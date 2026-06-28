"""Tests for storage.py — JSONLStorage"""

import pytest
from src.event_types import EventType, create_event
from src.storage import JSONLStorage, Storage


class TestStorageABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            Storage()

    def test_jsonl_storage_is_storage(self):
        # 验证 JSONLStorage 实现了 Storage 接口
        s = JSONLStorage("data/test")
        assert isinstance(s, Storage)


class TestJSONLStorage:
    @pytest.fixture
    def store(self, tmp_path):
        """每个测试使用独立的临时目录"""
        return JSONLStorage(str(tmp_path))

    def test_append_generates_event_id(self, store):
        """Storage.append() 应该生成 event_id"""
        e = create_event(type=EventType.CHAT, data={"content": "hello"}, person="小雨")
        assert e.event_id == ""                  # 创建时为空
        result = store.append(e)
        assert result.event_id != ""             # append 后应生成
        assert len(result.event_id) > 0

    def test_append_generates_recorded_at(self, store):
        """Storage.append() 应该生成 recorded_at"""
        e = create_event(type=EventType.CHAT, data={"content": "hello"})
        assert e.recorded_at == ""
        result = store.append(e)
        assert result.recorded_at != ""          # append 后应生成

        # recorded_at 应为合法的 UTC ISO 时间戳
        from datetime import datetime
        ts = datetime.fromisoformat(result.recorded_at)

    def test_append_preserves_occurred_at(self, store):
        """Storage.append() 不应该修改 occurred_at"""
        e = create_event(type=EventType.FACT, data={"content": "test"},
                         occurred_at="2025-01-01T00:00:00+00:00")
        result = store.append(e)
        assert result.occurred_at == "2025-01-01T00:00:00+00:00"

    def test_append_preserves_version(self, store):
        """Storage.append() 应该保留 version"""
        e = create_event(type=EventType.CHAT, data={}, version=1)
        result = store.append(e)
        assert result.version == 1

    def test_read_all_empty(self, store):
        """空 Event Store 应返回空迭代器"""
        events = list(store.read_all())
        assert events == []

    def test_append_and_read_all(self, store):
        """写入后应能完整读取"""
        e1 = store.append(create_event(type=EventType.CHAT, data={"content": "hi"}, person="小雨"))
        e2 = store.append(create_event(type=EventType.FACT, data={"content": "喜欢奶茶"}, person="小雨"))

        events = list(store.read_all())
        assert len(events) == 2
        assert events[0].event_id == e1.event_id
        assert events[1].event_id == e2.event_id
        # recorded_at 应按写入顺序递增
        assert events[1].recorded_at >= events[0].recorded_at

    def test_count(self, store):
        """count() 应返回正确数量"""
        assert store.count() == 0
        store.append(create_event(type=EventType.CHAT, data={}))
        assert store.count() == 1
        store.append(create_event(type=EventType.FACT, data={}))
        assert store.count() == 2

    def test_event_immutability_not_affected(self, store):
        """Storage 修改 event_id/recorded_at 使用 object.__setattr__
           因为 Event 是 frozen dataclass，正常赋值会抛异常，所以用底层绕过"""
        e = create_event(type=EventType.CHAT, data={})
        result = store.append(e)
        # result 应该有 event_id 和 recorded_at
        assert result.event_id
        assert result.recorded_at

    # ---- read_since（增量读取）----

    def test_read_since_returns_events_after_given_id(self, store):
        """read_since(id) 返回该 id 之后的所有事件"""
        e1 = store.append(create_event(type=EventType.CHAT, data={"i": 1}))
        e2 = store.append(create_event(type=EventType.CHAT, data={"i": 2}))
        e3 = store.append(create_event(type=EventType.CHAT, data={"i": 3}))

        # 从 e1 之后开始读
        remaining = list(store.read_since(e1.event_id))
        assert len(remaining) == 2
        assert remaining[0].event_id == e2.event_id
        assert remaining[1].event_id == e3.event_id

    def test_read_since_from_last_event_returns_empty(self, store):
        """read_since(最后一个id) 应返回空"""
        e1 = store.append(create_event(type=EventType.CHAT, data={}))
        remaining = list(store.read_since(e1.event_id))
        assert len(remaining) == 0

    def test_read_since_nonexistent_id_returns_empty(self, store):
        """read_since(不存在的id) 安全降级返回空"""
        store.append(create_event(type=EventType.CHAT, data={}))
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
            events.append(store.append(create_event(type=EventType.CHAT, data={"i": i})))

        remaining = list(store.read_since(events[0].event_id))
        assert len(remaining) == 4
        assert [r.data["i"] for r in remaining] == [1, 2, 3, 4]
