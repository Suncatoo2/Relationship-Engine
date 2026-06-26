"""Tests for projections/relationship.py"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event, RelationStage
from src.projections.relationship import (
    RelationshipProjection, RelationshipProfile,
    ChemistryRecord, MilestoneRecord, TimelineEntry,
)


@pytest.fixture
def proj():
    return RelationshipProjection()


def make_base_events():
    """基础事件集"""
    now = datetime.now(timezone.utc)
    return [
        # 10天前认识小雨
        create_event(type=EventType.PERSON, data={"action": "create", "tags": ["暧昧"]},
                     person="小雨", timestamp=(now - timedelta(days=10)).isoformat()),
        # 8天前进入认识阶段
        create_event(type=EventType.RELATION, data={"stage": "认识", "delta": 10, "event": "初次见面"},
                     person="小雨", timestamp=(now - timedelta(days=8)).isoformat()),
        # 5天前聊天
        create_event(type=EventType.CHAT, data={"content": "聊了一晚上"},
                     person="小雨", timestamp=(now - timedelta(days=5)).isoformat()),
        # 5天前好感度上升
        create_event(type=EventType.RELATION, data={"delta": 15, "event": "聊得很开心"},
                     person="小雨", timestamp=(now - timedelta(days=5)).isoformat()),
        # 3天前第一次约会
        create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 30, "event": "第一次约会"},
                     person="小雨", timestamp=(now - timedelta(days=3)).isoformat()),
        create_event(type=EventType.MILESTONE, data={"milestone_type": "first_date", "description": "一起看电影", "significance": 9},
                     person="小雨", timestamp=(now - timedelta(days=3)).isoformat()),
    ]


class TestEmpty:
    def test_empty(self, proj):
        assert proj.project([]) == {}


class TestBasicReplay:
    def test_basic_relationship(self, proj):
        events = make_base_events()
        result = proj.project(events)
        assert "小雨" in result
        p = result["小雨"]
        assert p.person_name == "小雨"
        assert p.stage == "暧昧"
        assert p.previous_stage == "认识"
        assert p.base_chemistry == 55  # 10 + 15 + 30
        assert p.relationship_type == "暧昧"

    def test_stage_changed_at(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.stage_changed_at  # 有时间戳
        assert p.previous_stage == "认识"


class TestChemistryHistory:
    def test_chemistry_history_recorded(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        assert len(p.chemistry_history) == 3
        assert p.chemistry_history[0].delta == 10
        assert p.chemistry_history[0].reason == "初次见面"
        assert p.chemistry_history[1].delta == 15
        assert p.chemistry_history[2].delta == 30

    def test_chemistry_history_has_event_id(self, proj):
        events = make_base_events()
        result = proj.project(events)
        for c in result["小雨"].chemistry_history:
            assert c.event_id  # 每条记录都有 event_id


class TestDecay:
    def test_decay_when_recent_contact(self, proj):
        """刚联系过，衰减应该很小"""
        events = make_base_events()  # 最后联系是3天前
        result = proj.project(events)
        p = result["小雨"]
        # 3天前联系，λ=0.05(暧昧)，factor=1/(1+0.05*3)=0.87
        # decay=55*0.87+5=52.85 → 52
        assert p.decay_chemistry >= 45
        assert p.decay_chemistry <= p.base_chemistry + p.floor

    def test_decay_with_old_contact(self, proj):
        """很久没联系，衰减应该明显"""
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={"tags": ["普通朋友"]},
                         person="老王", timestamp=(now - timedelta(days=60)).isoformat()),
            create_event(type=EventType.RELATION, data={"stage": "朋友", "delta": 50},
                         person="老王", timestamp=(now - timedelta(days=60)).isoformat()),
        ]
        result = proj.project(events)
        p = result["老王"]
        # 60天没联系，λ=0.02(普通朋友)
        # factor=1/(1+0.02*60)=0.45
        # decay=50*0.45+10=32.5 → 32
        assert p.decay_chemistry < p.base_chemistry
        assert p.decay_chemistry >= p.floor

    def test_floor_never_below(self, proj):
        """好感度永远不会低于 floor"""
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={"tags": ["暧昧"]},
                         person="小雨", timestamp=(now - timedelta(days=365)).isoformat()),
            create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 10},
                         person="小雨", timestamp=(now - timedelta(days=365)).isoformat()),
        ]
        result = proj.project(events)
        p = result["小雨"]
        assert p.decay_chemistry >= p.floor


class TestTimeline:
    def test_timeline_generated(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        assert len(p.timeline) > 0
        # 应该有阶段变化和事件
        types = {t.entry_type for t in p.timeline}
        assert "stage_change" in types

    def test_timeline_sorted(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        timestamps = [t.timestamp for t in p.timeline]
        assert timestamps == sorted(timestamps)

    def test_timeline_has_reason(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        stage_changes = [t for t in p.timeline if t.entry_type == "stage_change"]
        assert any(t.reason for t in stage_changes)


class TestMilestones:
    def test_milestones_recorded(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        assert len(p.milestones) == 1
        assert p.milestones[0].milestone_type == "first_date"
        assert p.milestones[0].description == "一起看电影"
        assert p.milestones[0].significance == 9


class TestTrend:
    def test_trend_warming(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={"tags": ["暧昧"]}, person="小雨"),
            create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 20},
                         person="小雨", timestamp=(now - timedelta(days=5)).isoformat()),
            create_event(type=EventType.RELATION, data={"delta": 15},
                         person="小雨", timestamp=(now - timedelta(days=2)).isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].trend == "升温"

    def test_trend_cooling(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={"tags": ["暧昧"]}, person="小雨"),
            create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": -20},
                         person="小雨", timestamp=(now - timedelta(days=5)).isoformat()),
            create_event(type=EventType.RELATION, data={"delta": -15},
                         person="小雨", timestamp=(now - timedelta(days=2)).isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].trend == "降温"

    def test_trend_stable(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={"tags": ["暧昧"]}, person="小雨"),
            create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 5},
                         person="小雨", timestamp=(now - timedelta(days=5)).isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].trend == "稳定"


class TestMetadata:
    def test_metadata_present(self, proj):
        events = make_base_events()
        result = proj.project(events)
        p = result["小雨"]
        assert "generated_at" in p.metadata
        assert "source_event_count" in p.metadata
        assert "version" in p.metadata
        assert p.metadata["source_event_count"] == len(events)


class TestDataclassOutput:
    def test_output_is_relationship_profile(self, proj):
        events = make_base_events()
        result = proj.project(events)
        assert isinstance(result["小雨"], RelationshipProfile)

    def test_to_dict(self, proj):
        events = make_base_events()
        result = proj.project(events)
        d = result["小雨"].to_dict()
        assert isinstance(d, dict)
        assert d["stage"] == "暧昧"
        assert d["base_chemistry"] == 55
        assert isinstance(d["chemistry_history"], list)
        assert isinstance(d["milestones"], list)
        assert isinstance(d["timeline"], list)


class TestProjectOne:
    def test_project_one(self, proj):
        events = make_base_events()
        p = proj.project_one(events, "小雨")
        assert p is not None
        assert p.stage == "暧昧"

    def test_project_one_not_found(self, proj):
        p = proj.project_one([], "不存在")
        assert p is None


class TestFullReplay:
    def test_full_scenario(self, proj):
        """完整场景：认识 → 聊天 → 暧昧 → 冷淡"""
        now = datetime.now(timezone.utc)
        events = [
            # 认识
            create_event(type=EventType.PERSON, data={"tags": ["暧昧"]}, person="小雨",
                         timestamp=(now - timedelta(days=30)).isoformat()),
            create_event(type=EventType.RELATION, data={"stage": "认识", "delta": 10, "event": "初次见面"},
                         person="小雨", timestamp=(now - timedelta(days=30)).isoformat()),
            # 聊天频繁
            create_event(type=EventType.CHAT, data={"content": "聊了一晚上"},
                         person="小雨", timestamp=(now - timedelta(days=25)).isoformat()),
            create_event(type=EventType.RELATION, data={"delta": 15, "event": "聊得很投缘"},
                         person="小雨", timestamp=(now - timedelta(days=25)).isoformat()),
            # 进入暧昧
            create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 30, "event": "第一次约会"},
                         person="小雨", timestamp=(now - timedelta(days=15)).isoformat()),
            create_event(type=EventType.MILESTONE, data={"milestone_type": "first_date", "description": "一起看电影", "significance": 9},
                         person="小雨", timestamp=(now - timedelta(days=15)).isoformat()),
        ]
        result = proj.project(events)
        p = result["小雨"]

        assert p.stage == "暧昧"
        assert p.previous_stage == "认识"
        assert p.base_chemistry == 55
        assert len(p.chemistry_history) == 3
        assert len(p.milestones) == 1
        assert len(p.timeline) >= 3
        assert p.relationship_type == "暧昧"
        assert p.metadata["source_event_count"] == len(events)
