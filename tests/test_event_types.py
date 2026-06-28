"""Tests for event_types.py"""

import pytest
from src.event_types import (
    Event, EventType, RelationStage, MilestoneType,
    GrowthCategory, FactCategory, EmotionLabel,
    DECAY_PARAMS, create_event,
)


class TestEvent:
    def test_create_event_auto_timestamps(self):
        e = create_event(type=EventType.CHAT, data={"role": "user", "content": "hello"}, person="小雨")
        assert e.occurred_at  # occurred_at 自动生成
        assert e.type == "chat"
        assert e.person == "小雨"
        assert e.data == {"role": "user", "content": "hello"}
        assert e.source == "user_input"
        # event_id 和 recorded_at 由 Storage 层在 append 时生成，创建时为空
        assert e.event_id == ""
        assert e.recorded_at == ""

    def test_create_event_version_default(self):
        e = create_event(type=EventType.CHAT, data={}, person="x")
        assert e.version == 1

    def test_create_event_custom_occurred_at(self):
        e = create_event(type=EventType.FACT, data={"content": "test"}, occurred_at="2025-01-01T00:00:00")
        assert e.occurred_at == "2025-01-01T00:00:00"

    def test_create_event_custom_source(self):
        e = create_event(type=EventType.EMOTION, data={}, source="ai_detected")
        assert e.source == "ai_detected"

    def test_event_to_dict(self):
        e = create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨")
        d = e.to_dict()
        assert d["type"] == "person"
        assert d["person"] == "小雨"
        assert d["data"] == {"action": "create"}

    def test_event_to_dict_empty_person(self):
        e = create_event(type=EventType.REMINDER, data={"message": "test"})
        d = e.to_dict()
        assert "person" not in d

    def test_event_from_dict_new_format(self):
        d = {
            "event_id": "test-id",
            "occurred_at": "2025-01-01T00:00:00",
            "type": "chat",
            "data": {"role": "user", "content": "hi"},
            "person": "小雨",
            "source": "user_input",
            "version": 1,
            "recorded_at": "2025-01-01T00:00:01",
        }
        e = Event.from_dict(d)
        assert e.event_id == "test-id"
        assert e.occurred_at == "2025-01-01T00:00:00"
        assert e.recorded_at == "2025-01-01T00:00:01"
        assert e.version == 1
        assert e.type == "chat"
        assert e.person == "小雨"

    def test_event_from_dict_no_person(self):
        d = {"event_id": "x", "occurred_at": "2025-01-01T00:00:00", "type": "reminder", "data": {}, "version": 1}
        e = Event.from_dict(d)
        assert e.person == ""

    def test_roundtrip_to_dict_from_dict(self):
        e1 = create_event(type=EventType.FACT, data={"content": "喜欢奶茶", "category": "preference"}, person="小雨")
        d = e1.to_dict()
        e2 = Event.from_dict(d)
        assert e1.event_id == e2.event_id
        assert e1.type == e2.type
        assert e1.person == e2.person
        assert e1.data == e2.data


class TestEventTypes:
    def test_all_event_types_exist(self):
        expected = {"person", "chat", "fact", "emotion", "relation", "milestone", "growth", "reminder"}
        actual = {t.value for t in EventType}
        assert actual == expected

    def test_create_each_type(self):
        for t in EventType:
            e = create_event(type=t, data={"test": True}, person="test")
            assert e.type == t.value


    def test_from_dict_backward_compat_old_format(self):
        """旧格式（id / timestamp）应被兼容解析"""
        d = {
            "id": "old-id",
            "timestamp": "2024-06-01T00:00:00",
            "type": "fact",
            "data": {"content": "old data"},
        }
        e = Event.from_dict(d)
        assert e.event_id == "old-id"
        assert e.occurred_at == "2024-06-01T00:00:00"
        assert e.type == "fact"



    def test_from_dict_backward_compat_old_format(self):
        """旧格式（id / timestamp）应被兼容解析"""
        d = {
            "id": "old-id",
            "timestamp": "2024-06-01T00:00:00",
            "type": "fact",
            "data": {"content": "old data"},
        }
        e = Event.from_dict(d)
        assert e.event_id == "old-id"
        assert e.occurred_at == "2024-06-01T00:00:00"
        assert e.type == "fact"



class TestEnums:
    def test_relation_stages(self):
        assert RelationStage.STRANGER.value == "陌生人"
        assert RelationStage.AMBIGUOUS.value == "暧昧"

    def test_milestone_types(self):
        assert MilestoneType.FIRST_MEET.value == "first_meet"
        assert MilestoneType.CUSTOM.value == "custom"

    def test_growth_categories(self):
        assert GrowthCategory.SKILL.value == "skill"

    def test_fact_categories(self):
        assert FactCategory.PREFERENCE.value == "preference"

    def test_emotion_labels(self):
        assert EmotionLabel.HAPPY.value == "开心"


class TestDecayParams:
    def test_all_stages_have_params(self):
        assert "家人" in DECAY_PARAMS
        assert "暧昧" in DECAY_PARAMS

    def test_params_structure(self):
        for name, params in DECAY_PARAMS.items():
            assert "lambda" in params
            assert "floor" in params
            assert params["lambda"] > 0
            assert 0 <= params["floor"] <= 100
