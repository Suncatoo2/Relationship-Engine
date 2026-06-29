"""Tests for event_log.py"""

import os
import time
import tempfile
import pytest
from src.event_types import EventType, create_event
from src.event_log import EventLog


@pytest.fixture
def log(tmp_path):
    """每个测试使用独立的临时目录"""
    return EventLog(str(tmp_path))


@pytest.fixture
def populated_log(log):
    """预填充一些事件的日志"""
    log.append(create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1998-06-15"}, person="小雨"))
    log.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "今天一起吃饭吧"}, person="小雨"))
    log.append(create_event(type=EventType.CHAT, data={"role": "assistant", "content": "好呀，吃什么？"}, person="小雨"))
    log.append(create_event(type=EventType.FACT, data={"content": "喜欢喝抹茶拿铁", "category": "preference"}, person="小雨"))
    log.append(create_event(type=EventType.EMOTION, data={"valence": 0.8, "label": "开心"}, person="小雨"))
    log.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "今天天气不错"}, person="老王"))
    log.append(create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 20}, person="小雨"))
    return log


class TestEventLogAppendAndRead:
    def test_append_and_read_all(self, log):
        e1 = create_event(type=EventType.CHAT, data={"content": "hello"}, person="小雨")
        e2 = create_event(type=EventType.FACT, data={"content": "喜欢奶茶"}, person="小雨")
        log.append(e1)
        log.append(e2)
        events = log.read_all()
        assert len(events) == 2
        assert events[0].event_id == e1.event_id
        assert events[1].event_id == e2.event_id

    def test_read_all_empty_log(self, log):
        assert log.read_all() == []

    def test_append_preserves_order(self, log):
        ids = []
        for i in range(10):
            e = create_event(type=EventType.CHAT, data={"i": i}, person="test")
            log.append(e)
            ids.append(e.event_id)
        events = log.read_all()
        assert [e.event_id for e in events] == ids

    def test_append_is_persistent(self, tmp_path):
        log1 = EventLog(str(tmp_path))
        e = create_event(type=EventType.FACT, data={"content": "test"}, person="x")
        log1.append(e)

        # 新实例应该能读到
        log2 = EventLog(str(tmp_path))
        events = log2.read_all()
        assert len(events) == 1
        assert events[0].event_id == e.event_id


class TestReadByType:
    def test_read_by_type(self, populated_log):
        chats = populated_log.read_by_type(EventType.CHAT)
        assert len(chats) == 3
        assert all(e.type == "chat" for e in chats)

    def test_read_by_type_no_match(self, populated_log):
        growths = populated_log.read_by_type(EventType.GROWTH)
        assert len(growths) == 0

    def test_read_by_type_person(self, populated_log):
        persons = populated_log.read_by_type(EventType.PERSON)
        assert len(persons) == 1
        assert persons[0].data["action"] == "create"


class TestReadByPerson:
    def test_read_by_person(self, populated_log):
        xiaoyu = populated_log.read_by_person("小雨")
        assert len(xiaoyu) == 6
        assert all(e.person == "小雨" for e in xiaoyu)

    def test_read_by_person_other(self, populated_log):
        laowang = populated_log.read_by_person("老王")
        assert len(laowang) == 1
        assert laowang[0].person == "老王"

    def test_read_by_person_not_found(self, populated_log):
        assert populated_log.read_by_person("不存在") == []


class TestReadRecent:
    def test_read_recent_all(self, log):
        # 所有事件都是"现在"创建的，应该全部在最近 1 天内
        log.append(create_event(type=EventType.CHAT, data={}, person="x"))
        events = log.read_recent(days=1)
        assert len(events) == 1

    def test_read_recent_old_event(self, log):
        # 创建一个很久以前的事件
        old = create_event(
            type=EventType.FACT,
            data={"content": "old"},
            person="x",
            occurred_at="2020-01-01T00:00:00Z",
        )
        log.append(old)
        # 创建一个现在的事件
        now = create_event(type=EventType.FACT, data={"content": "new"}, person="x")
        log.append(now)

        recent = log.read_recent(days=1)
        assert len(recent) == 1
        assert recent[0].data["content"] == "new"

    def test_read_recent_empty(self, log):
        assert log.read_recent(days=30) == []


class TestSearch:
    def test_search_content(self, populated_log):
        results = populated_log.search("抹茶")
        assert len(results) == 1
        assert "抹茶" in results[0].data["content"]

    def test_search_person(self, populated_log):
        results = populated_log.search("老王")
        assert len(results) == 1
        assert results[0].person == "老王"

    def test_search_case_insensitive(self, log):
        log.append(create_event(type=EventType.FACT, data={"content": "Hello World"}, person="test"))
        assert len(log.search("hello")) == 1
        assert len(log.search("WORLD")) == 1

    def test_search_no_match(self, populated_log):
        assert populated_log.search("不存在的关键词") == []

    def test_search_in_list_values(self, log):
        log.append(create_event(type=EventType.PERSON, data={"tags": ["室友", "同学"]}, person="小雨"))
        results = log.search("室友")
        assert len(results) == 1


class TestCount:
    def test_count_empty(self, log):
        assert log.count() == 0

    def test_count(self, populated_log):
        assert populated_log.count() == 7


class TestClear:
    def test_clear(self, populated_log):
        assert populated_log.count() == 7
        populated_log.clear()
        assert populated_log.count() == 0
        assert populated_log.read_all() == []


class TestIterators:
    def test_iter_events(self, populated_log):
        events = list(populated_log.iter_events())
        assert len(events) == 7

    def test_iter_events_empty(self, log):
        assert list(log.iter_events()) == []

    def test_iter_events_same_as_read_all(self, populated_log):
        iter_ids = [e.event_id for e in populated_log.iter_events()]
        read_ids = [e.event_id for e in populated_log.read_all()]
        assert iter_ids == read_ids

    def test_iter_by_type(self, populated_log):
        chats = list(populated_log.iter_by_type(EventType.CHAT))
        assert len(chats) == 3
        assert all(e.type == "chat" for e in chats)

    def test_iter_by_person(self, populated_log):
        xiaoyu = list(populated_log.iter_by_person("小雨"))
        assert len(xiaoyu) == 6
        assert all(e.person == "小雨" for e in xiaoyu)

    def test_iter_is_lazy(self, log):
        """验证迭代器是惰性的：提前 break 不会读完全部文件"""
        for i in range(100):
            log.append(create_event(type=EventType.CHAT, data={"i": i}, person="test"))
        count = 0
        for e in log.iter_events():
            count += 1
            if count == 5:
                break
        assert count == 5  # 只读了 5 条，不是 100 条


class TestPerformance:
    def test_1000_events_append(self, log):
        start = time.time()
        for i in range(1000):
            log.append(create_event(type=EventType.CHAT, data={"i": i}, person="test"))
        elapsed = time.time() - start
        assert elapsed < 2.0, f"1000 事件追加耗时 {elapsed:.2f}s，超过 2 秒"

    def test_1000_events_read(self, log):
        for i in range(1000):
            log.append(create_event(type=EventType.CHAT, data={"i": i}, person="test"))
        start = time.time()
        events = log.read_all()
        elapsed = time.time() - start
        assert len(events) == 1000
        assert elapsed < 1.0, f"读取 1000 事件耗时 {elapsed:.2f}s，超过 1 秒"
