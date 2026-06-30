"""Tests for storage.py — JSONLStorage"""

import pytest
from src.event_types import EventType, create_event
from src.storage import JSONLStorage, Storage, StorageCapability


# ---- Helpers ----

def _cap() -> StorageCapability:
    """创建合法的 test capability token"""
    return StorageCapability(_token="pipeline:test_token")


def _mk_store(path, token="pipeline:test_token") -> JSONLStorage:
    """创建带 capability 的 JSONLStorage"""
    return JSONLStorage(str(path), capability_token=token)


class TestStorageABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            Storage()

    def test_jsonl_storage_is_storage(self):
        # 验证 JSONLStorage 实现了 Storage 接口
        s = _mk_store("data/test")
        assert isinstance(s, Storage)


class TestJSONLStorage:
    @pytest.fixture
    def store(self, tmp_path):
        """每个测试使用独立的临时目录"""
        return _mk_store(tmp_path)

    def test_append_generates_event_id(self, store):
        """Storage.append() 应该生成 event_id"""
        e = create_event(type=EventType.CHAT, data={"content": "hello"}, person="小雨")
        assert e.event_id == ""                  # 创建时为空
        result = store.append(e, capability=_cap())
        assert result.event_id != ""             # append 后应生成
        assert len(result.event_id) > 0

    def test_append_generates_recorded_at(self, store):
        """Storage.append() 应该生成 recorded_at"""
        e = create_event(type=EventType.CHAT, data={"content": "hello"})
        assert e.recorded_at == ""
        result = store.append(e, capability=_cap())
        assert result.recorded_at != ""          # append 后应生成

        # recorded_at 应为合法的 UTC ISO 时间戳
        from datetime import datetime
        ts = datetime.fromisoformat(result.recorded_at)

    def test_append_preserves_occurred_at(self, store):
        """Storage.append() 不应该修改 occurred_at"""
        e = create_event(type=EventType.FACT, data={"content": "test"},
                         occurred_at="2025-01-01T00:00:00+00:00")
        result = store.append(e, capability=_cap())
        assert result.occurred_at == "2025-01-01T00:00:00+00:00"

    def test_append_preserves_version(self, store):
        """Storage.append() 应该保留 version"""
        e = create_event(type=EventType.CHAT, data={}, version=1)
        result = store.append(e, capability=_cap())
        assert result.version == 1

    def test_read_all_empty(self, store):
        """空 Event Store 应返回空迭代器"""
        events = list(store.read_all())
        assert events == []

    def test_append_and_read_all(self, store):
        """写入后应能完整读取"""
        e1 = store.append(create_event(type=EventType.CHAT, data={"content": "hi"}, person="小雨"), capability=_cap())
        e2 = store.append(create_event(type=EventType.FACT, data={"content": "喜欢奶茶"}, person="小雨"), capability=_cap())

        events = list(store.read_all())
        assert len(events) == 2
        assert events[0].event_id == e1.event_id
        assert events[1].event_id == e2.event_id
        # recorded_at 应按写入顺序递增
        assert events[1].recorded_at >= events[0].recorded_at

    def test_count(self, store):
        """count() 应返回正确数量"""
        assert store.count() == 0
        store.append(create_event(type=EventType.CHAT, data={}), capability=_cap())
        assert store.count() == 1
        store.append(create_event(type=EventType.FACT, data={}), capability=_cap())
        assert store.count() == 2

    def test_event_immutability_not_affected(self, store):
        """Storage 修改 event_id/recorded_at 使用 object.__setattr__
           因为 Event 是 frozen dataclass，正常赋值会抛异常，所以用底层绕过"""
        e = create_event(type=EventType.CHAT, data={})
        result = store.append(e, capability=_cap())
        # result 应该有 event_id 和 recorded_at
        assert result.event_id
        assert result.recorded_at

    # ---- read_since（增量读取）----

    def test_read_since_returns_events_after_given_id(self, store):
        """read_since(id) 返回该 id 之后的所有事件"""
        e1 = store.append(create_event(type=EventType.CHAT, data={"i": 1}), capability=_cap())
        e2 = store.append(create_event(type=EventType.CHAT, data={"i": 2}), capability=_cap())
        e3 = store.append(create_event(type=EventType.CHAT, data={"i": 3}), capability=_cap())

        # 从 e1 之后开始读
        remaining = list(store.read_since(e1.event_id))
        assert len(remaining) == 2
        assert remaining[0].event_id == e2.event_id
        assert remaining[1].event_id == e3.event_id

    def test_read_since_from_last_event_returns_empty(self, store):
        """read_since(最后一个id) 应返回空"""
        e1 = store.append(create_event(type=EventType.CHAT, data={}), capability=_cap())
        remaining = list(store.read_since(e1.event_id))
        assert len(remaining) == 0

    def test_read_since_nonexistent_id_returns_empty(self, store):
        """read_since(不存在的id) 安全降级返回空"""
        store.append(create_event(type=EventType.CHAT, data={}), capability=_cap())
        remaining = list(store.read_since("nonexistent-id"))
        assert len(remaining) == 0

    def test_read_since_empty_store(self, store):
        """空 store 的 read_since 返回空"""
        remaining = list(store.read_since("any-id"))
        assert len(remaining) == 0

    def test_read_since_from_first_returns_all_after(self, store):
        """从第一个 event 之后读取，应返回除第一个外的所有事件"""
        events = []
        for i in range(5):
            events.append(store.append(create_event(type=EventType.CHAT, data={"i": i}), capability=_cap()))

        remaining = list(store.read_since(events[0].event_id))
        assert len(remaining) == 4
        assert [r.data["i"] for r in remaining] == [1, 2, 3, 4]

    # ---- WAL + Crash Recovery ----

    def test_wal_recovery_on_startup(self, tmp_path):
        """模拟 crash: WAL 文件存在时，启动自动恢复"""
        import os
        cap = _cap()
        store = _mk_store(tmp_path)

        # 写入事件（正常情况下 WAL 会被清除）
        store.append(event=create_event(type=EventType.CHAT, data={"msg": "normal"}), capability=cap)
        assert not os.path.exists(store.wal_file), "正常写入后 WAL 应已清除"

        # 模拟 crash: 手动创建 WAL 文件
        wal_event = create_event(type=EventType.CHAT, data={"msg": "recovered"}, person="WAL", occurred_at="2026-06-30T00:00:00+00:00")
        # 先生成 event_id 和 recorded_at
        object.__setattr__(wal_event, "event_id", "wal-recovery-test-001")
        object.__setattr__(wal_event, "recorded_at", "2026-06-30T12:00:00+00:00")
        import json as _json
        with open(store.wal_file, "w", encoding="utf-8") as f:
            f.write(_json.dumps(wal_event.to_dict(), ensure_ascii=False) + "\n")

        # 重新创建 store（模拟重启）
        store2 = _mk_store(tmp_path)
        events2 = list(store2.read_all())
        # 原始 1 个 + WAL 恢复 1 个 = 2
        assert len(events2) == 2, "应恢复 WAL 中的事件，实际: {}".format(len(events2))
        recovered = [e for e in events2 if e.event_id == "wal-recovery-test-001"]
        assert len(recovered) == 1, "WAL 恢复的事件应存在"
        assert not os.path.exists(store2.wal_file), "恢复后 WAL 应已清除"

    def test_corrupted_line_skipped(self, tmp_path):
        """损坏的 JSON 行应被跳过，不中断读取"""
        cap = _cap()
        store = _mk_store(tmp_path)

        # 写正常事件
        store.append(event=create_event(type=EventType.CHAT, data={"msg": "good"}), capability=cap)

        # 手动写入损坏行
        with open(store.log_file, "a", encoding="utf-8") as f:
            f.write("this is not valid json\n")
            f.write('{"event_id":"partial"\n')  # 不完整的 JSON

        store.append(event=create_event(type=EventType.CHAT, data={"msg": "also good"}), capability=cap)

        events = list(store.read_all())
        assert len(events) == 2, "损坏行应被跳过，实际: {}".format(len(events))
        h = store.health()
        assert h["corrupted_records"] >= 1

    def test_health_on_clean_store(self, tmp_path):
        """干净的 store health 报告"""
        cap = _cap()
        store = _mk_store(tmp_path)
        store.append(event=create_event(type=EventType.CHAT, data={"msg": "hello"}), capability=cap)

        h = store.health()
        assert h["status"] == "healthy"
        assert h["event_count"] == 1
        assert h["corrupted_records"] == 0
        assert h["wal_dirty"] is False
        assert h["current_size_bytes"] > 0

    def test_capability_guard_rejects_none(self, tmp_path):
        """无 capability 的 append 应被拒绝"""
        store = _mk_store(tmp_path, token="pipeline:real_token")
        from src.storage import ArchitectureViolation
        try:
            store.append(event=create_event(type=EventType.CHAT, data={}))
            assert False, "应该抛出 ArchitectureViolation"
        except ArchitectureViolation:
            pass  # expected

    def test_capability_guard_rejects_wrong_token(self, tmp_path):
        """错误的 capability token 应被拒绝"""
        store = _mk_store(tmp_path, token="pipeline:real_token")
        wrong_cap = StorageCapability(_token="pipeline:wrong_token")
        from src.storage import ArchitectureViolation
        try:
            store.append(event=create_event(type=EventType.CHAT, data={}), capability=wrong_cap)
            assert False, "应该抛出 ArchitectureViolation"
        except ArchitectureViolation:
            pass  # expected
