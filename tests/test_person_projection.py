"""Tests for projections/person.py"""

import pytest
from src.event_types import EventType, create_event
from src.projections.person import PersonProjection, PersonProfile, FactRecord


@pytest.fixture
def proj():
    return PersonProjection()


class TestPersonProjectionEmpty:
    def test_empty_events(self, proj):
        result = proj.project([])
        assert result == {}

    def test_no_person_events(self, proj):
        events = [create_event(type=EventType.CHAT, data={"content": "hi"}, person="小雨")]
        result = proj.project(events)
        assert result == {}


class TestPersonCreation:
    def test_create_person(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1998-06-15"}, person="小雨"),
        ]
        result = proj.project(events)
        assert "小雨" in result
        p = result["小雨"]
        assert p.name == "小雨"
        assert p.birthday == "1998-06-15"
        assert p.first_met  # 自动生成
        assert p.facts == []
        assert p.fact_count == 0

    def test_create_multiple_persons(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"action": "create"}, person="老王"),
        ]
        result = proj.project(events)
        assert len(result) == 2
        assert "小雨" in result
        assert "老王" in result


class TestPersonUpdate:
    def test_update_nickname(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"nickname": "小鱼儿"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].nickname == "小鱼儿"

    def test_update_tags(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"tags": ["室友", "同学"]}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].tags == ["室友", "同学"]

    def test_incremental_update_preserves_existing(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1998-06-15"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"nickname": "小鱼儿"}, person="小雨"),
        ]
        result = proj.project(events)
        p = result["小雨"]
        assert p.birthday == "1998-06-15"  # 保留
        assert p.nickname == "小鱼儿"       # 新增

    def test_update_notes(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"notes": "喜欢画画"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].notes == "喜欢画画"


class TestFactEvents:
    def test_add_fact(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.FACT, data={"content": "喜欢奶茶", "category": "preference", "importance": 8}, person="小雨"),
        ]
        result = proj.project(events)
        p = result["小雨"]
        assert p.fact_count == 1
        assert p.facts[0].content == "喜欢奶茶"
        assert p.facts[0].category == "preference"
        assert p.facts[0].importance == 8

    def test_add_multiple_facts(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.FACT, data={"content": "喜欢奶茶", "category": "preference"}, person="小雨"),
            create_event(type=EventType.FACT, data={"content": "怕打雷", "category": "secret", "importance": 9}, person="小雨"),
            create_event(type=EventType.FACT, data={"content": "画画很好", "category": "hobby"}, person="小雨"),
        ]
        result = proj.project(events)
        p = result["小雨"]
        assert p.fact_count == 3
        assert p.facts[0].content == "喜欢奶茶"
        assert p.facts[1].content == "怕打雷"
        assert p.facts[2].content == "画画很好"

    def test_fact_without_prior_person_event(self, proj):
        """fact 事件应该自动创建人物"""
        events = [
            create_event(type=EventType.FACT, data={"content": "喜欢奶茶"}, person="小雨"),
        ]
        result = proj.project(events)
        assert "小雨" in result
        assert result["小雨"].fact_count == 1


class TestProjectOne:
    def test_project_one(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"action": "create"}, person="老王"),
        ]
        p = proj.project_one(events, "小雨")
        assert p is not None
        assert p.name == "小雨"

    def test_project_one_not_found(self, proj):
        events = [create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨")]
        p = proj.project_one(events, "不存在")
        assert p is None


class TestReplayOrder:
    def test_later_person_event_overrides(self, proj):
        """后面的 person 事件应该覆盖前面的同名字段"""
        events = [
            create_event(type=EventType.PERSON, data={"action": "create", "nickname": "A"}, person="小雨"),
            create_event(type=EventType.PERSON, data={"nickname": "B"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].nickname == "B"

    def test_first_met_preserved(self, proj):
        """first_met 应该保持第一个 person 事件的时间"""
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨",
                         timestamp="2025-01-01T00:00:00+00:00"),
            create_event(type=EventType.PERSON, data={"nickname": "小鱼儿"}, person="小雨",
                         timestamp="2025-06-01T00:00:00+00:00"),
        ]
        result = proj.project(events)
        assert result["小雨"].first_met == "2025-01-01T00:00:00+00:00"


class TestDataclassOutput:
    def test_output_is_person_profile(self, proj):
        events = [create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨")]
        result = proj.project(events)
        assert isinstance(result["小雨"], PersonProfile)

    def test_fact_is_fact_record(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨"),
            create_event(type=EventType.FACT, data={"content": "test"}, person="小雨"),
        ]
        result = proj.project(events)
        assert isinstance(result["小雨"].facts[0], FactRecord)

    def test_to_dict(self, proj):
        events = [
            create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1998-06-15"}, person="小雨"),
            create_event(type=EventType.FACT, data={"content": "喜欢奶茶", "category": "preference"}, person="小雨"),
        ]
        result = proj.project(events)
        d = result["小雨"].to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "小雨"
        assert d["birthday"] == "1998-06-15"
        assert len(d["facts"]) == 1
        assert d["facts"][0]["content"] == "喜欢奶茶"


class TestFullReplay:
    def test_full_replay_scenario(self, proj):
        """完整场景：认识 → 记忆 → 更新 → 多条事实"""
        events = [
            # 第一天：认识小雨
            create_event(type=EventType.PERSON,
                         data={"action": "create", "birthday": "1998-06-15", "tags": ["口腔同学"]},
                         person="小雨", timestamp="2025-01-15T10:00:00+00:00"),
            # 第三天：记住她喜欢奶茶
            create_event(type=EventType.FACT,
                         data={"content": "喜欢喝抹茶拿铁", "category": "preference", "importance": 8},
                         person="小雨", timestamp="2025-01-18T09:00:00+00:00"),
            # 第七天：更新昵称
            create_event(type=EventType.PERSON,
                         data={"nickname": "小鱼儿"},
                         person="小雨", timestamp="2025-01-22T14:00:00+00:00"),
            # 第十天：又记住一件事
            create_event(type=EventType.FACT,
                         data={"content": "怕打雷", "category": "secret", "importance": 9},
                         person="小雨", timestamp="2025-01-25T22:00:00+00:00"),
        ]
        result = proj.project(events)
        p = result["小雨"]

        assert p.name == "小雨"
        assert p.nickname == "小鱼儿"
        assert p.birthday == "1998-06-15"
        assert p.tags == ["口腔同学"]
        assert p.first_met == "2025-01-15T10:00:00+00:00"
        assert p.fact_count == 2
        assert p.facts[0].content == "喜欢喝抹茶拿铁"
        assert p.facts[1].content == "怕打雷"
        assert p.last_updated == "2025-01-25T22:00:00+00:00"
