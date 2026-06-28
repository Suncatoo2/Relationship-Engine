"""Tests for projections/base.py"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.base import Projection


# ---- 用于测试的具体子类 ----

class CountProjection(Projection):
    """测试用：统计各类型事件数量"""
    def project(self, events):
        return self.count_by_type(events)


class PersonListProjection(Projection):
    """测试用：列出所有人物"""
    def project(self, events):
        return {"persons": self.unique_persons(events)}


# ---- 测试数据 ----

def make_events():
    """生成测试事件集"""
    now = datetime.now(timezone.utc)
    return [
        create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨",
                     occurred_at=(now - timedelta(days=10)).isoformat()),
        create_event(type=EventType.CHAT, data={"content": "你好"}, person="小雨",
                     occurred_at=(now - timedelta(days=5)).isoformat()),
        create_event(type=EventType.CHAT, data={"content": "吃饭了吗"}, person="小雨",
                     occurred_at=(now - timedelta(days=2)).isoformat()),
        create_event(type=EventType.FACT, data={"content": "喜欢奶茶", "category": "preference"}, person="小雨",
                     occurred_at=(now - timedelta(days=3)).isoformat()),
        create_event(type=EventType.EMOTION, data={"valence": 0.8, "label": "开心"}, person="小雨",
                     occurred_at=(now - timedelta(days=1)).isoformat()),
        create_event(type=EventType.CHAT, data={"content": "天气不错"}, person="老王",
                     occurred_at=(now - timedelta(days=8)).isoformat()),
        create_event(type=EventType.RELATION, data={"stage": "朋友", "delta": 10}, person="老王",
                     occurred_at=(now - timedelta(days=60)).isoformat()),
        create_event(type=EventType.GROWTH, data={"title": "学会Python", "category": "skill"}, person="我自己",
                     occurred_at=(now - timedelta(days=30)).isoformat()),
    ]


@pytest.fixture
def events():
    return make_events()


# ---- 抽象基类验证 ----

class TestProjectionABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            Projection()

    def test_subclass_must_implement_project(self):
        class Incomplete(Projection):
            pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_can_be_instantiated(self):
        p = CountProjection()
        assert p is not None


# ---- filter_by_type ----

class TestFilterByType:
    def test_filter_chat(self, events):
        chats = Projection.filter_by_type(events, EventType.CHAT)
        assert len(chats) == 3
        assert all(e.type == "chat" for e in chats)

    def test_filter_person(self, events):
        persons = Projection.filter_by_type(events, EventType.PERSON)
        assert len(persons) == 1

    def test_filter_no_match(self, events):
        milestones = Projection.filter_by_type(events, EventType.MILESTONE)
        assert len(milestones) == 0

    def test_filter_preserves_input_order(self, events):
        chats = Projection.filter_by_type(events, EventType.CHAT)
        assert len(chats) == 3
        # filter 保持输入列表的顺序（不是时间顺序）
        assert chats == [events[1], events[2], events[5]]


# ---- filter_by_person ----

class TestFilterByPerson:
    def test_filter_xiaoyu(self, events):
        xiaoyu = Projection.filter_by_person(events, "小雨")
        assert len(xiaoyu) == 5
        assert all(e.person == "小雨" for e in xiaoyu)

    def test_filter_laowang(self, events):
        laowang = Projection.filter_by_person(events, "老王")
        assert len(laowang) == 2

    def test_filter_not_found(self, events):
        assert Projection.filter_by_person(events, "不存在") == []


# ---- filter_by_days ----

class TestFilterByDays:
    def test_filter_recent_3_days(self, events):
        recent = Projection.filter_by_days(events, days=3)
        # 2天前和1天前的事件应该保留
        assert len(recent) == 2

    def test_filter_recent_7_days(self, events):
        recent = Projection.filter_by_days(events, days=7)
        # 5天前、3天前、2天前、1天前的事件应该保留（共4个）
        assert len(recent) == 4

    def test_filter_recent_0_days(self, events):
        recent = Projection.filter_by_days(events, days=0)
        # 只有今天的事件（1天前的不算）
        assert len(recent) == 0


# ---- sort_by_time ----

class TestSortByTime:
    def test_sort_descending(self, events):
        sorted_events = Projection.sort_by_time(events, desc=True)
        for i in range(len(sorted_events) - 1):
            ts1 = datetime.fromisoformat(sorted_events[i].occurred_at)
            ts2 = datetime.fromisoformat(sorted_events[i + 1].occurred_at)
            assert ts1 >= ts2

    def test_sort_ascending(self, events):
        sorted_events = Projection.sort_by_time(events, desc=False)
        for i in range(len(sorted_events) - 1):
            ts1 = datetime.fromisoformat(sorted_events[i].occurred_at)
            ts2 = datetime.fromisoformat(sorted_events[i + 1].occurred_at)
            assert ts1 <= ts2

    def test_sort_empty(self):
        assert Projection.sort_by_time([]) == []


# ---- days_since ----

class TestDaysSince:
    def test_days_since_recent(self):
        now = datetime.now(timezone.utc).isoformat()
        assert Projection.days_since(now) == 0

    def test_days_since_5_days_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        assert Projection.days_since(ts) == 5

    def test_days_since_invalid(self):
        assert Projection.days_since("invalid") == -1

    def test_days_since_empty(self):
        assert Projection.days_since("") == -1


# ---- get_latest ----

class TestGetLatest:
    def test_get_latest(self, events):
        latest = Projection.get_latest(events)
        assert latest is not None
        assert latest.type == "emotion"  # 1天前的事件

    def test_get_latest_empty(self):
        assert Projection.get_latest([]) is None


# ---- unique_persons ----

class TestUniquePersons:
    def test_unique_persons(self, events):
        persons = Projection.unique_persons(events)
        assert set(persons) == {"小雨", "老王", "我自己"}

    def test_unique_persons_preserves_order(self, events):
        persons = Projection.unique_persons(events)
        assert persons[0] == "小雨"  # 第一个出现的

    def test_unique_persons_empty(self):
        assert Projection.unique_persons([]) == []


# ---- count_by_type ----

class TestCountByType:
    def test_count_by_type(self, events):
        counts = Projection.count_by_type(events)
        assert counts["chat"] == 3
        assert counts["person"] == 1
        assert counts["fact"] == 1
        assert counts["emotion"] == 1
        assert counts["relation"] == 1
        assert counts["growth"] == 1

    def test_count_by_type_empty(self):
        assert Projection.count_by_type([]) == {}


# ---- 子类集成 ----

class TestSubclassIntegration:
    def test_count_projection(self, events):
        p = CountProjection()
        result = p.project(events)
        assert result["chat"] == 3
        assert result["person"] == 1

    def test_person_list_projection(self, events):
        p = PersonListProjection()
        result = p.project(events)
        assert set(result["persons"]) == {"小雨", "老王", "我自己"}
