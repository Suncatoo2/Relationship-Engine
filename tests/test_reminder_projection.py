"""Tests for projections/reminder.py"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.reminder import (
    ReminderProjection, ReminderProfile, ReminderItem,
    ReminderTrigger, ReminderType, ReminderStatus, TriggerType, Urgency,
)


@pytest.fixture
def proj():
    return ReminderProjection()


class TestEmpty:
    def test_empty(self, proj):
        result = proj.project([])
        assert result.total == 0
        assert result.items == []


class TestBirthdayReminder:
    def test_birthday_soon(self, proj):
        now = datetime.now(timezone.utc)
        # 生日就在3天后
        bd = (now + timedelta(days=3)).strftime("%Y-%m-%d")
        events = [
            create_event(type=EventType.PERSON, data={"birthday": bd}, person="小雨"),
        ]
        result = proj.project(events)
        birthday_items = [i for i in result.items if "生日" in i.message]
        assert len(birthday_items) == 1
        assert birthday_items[0].urgency == Urgency.HIGH
        assert birthday_items[0].trigger.type == TriggerType.DATE

    def test_birthday_today(self, proj):
        now = datetime.now(timezone.utc)
        bd = now.strftime("%Y-%m-%d")
        events = [create_event(type=EventType.PERSON, data={"birthday": bd}, person="小雨")]
        result = proj.project(events)
        birthday_items = [i for i in result.items if "生日" in i.message]
        assert len(birthday_items) == 1
        assert "今天" in birthday_items[0].message

    def test_birthday_far_away(self, proj):
        now = datetime.now(timezone.utc)
        bd = (now + timedelta(days=60)).strftime("%Y-%m-%d")
        events = [create_event(type=EventType.PERSON, data={"birthday": bd}, person="小雨")]
        result = proj.project(events)
        birthday_items = [i for i in result.items if "生日" in i.message]
        assert len(birthday_items) == 0  # 超过7天不提醒


class TestRelationshipReminder:
    def test_lost_contact(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨"),
            create_event(type=EventType.CHAT, data={"content": "晚安"}, person="小雨",
                         timestamp=(now - timedelta(days=10)).isoformat()),
        ]
        result = proj.project(events)
        rel_items = [i for i in result.items if i.reminder_type == ReminderType.RELATIONSHIP]
        assert len(rel_items) == 1
        assert "10天" in rel_items[0].message
        assert rel_items[0].trigger.type == TriggerType.INACTIVITY

    def test_no_lost_contact(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨"),
            create_event(type=EventType.CHAT, data={"content": "hi"}, person="小雨",
                         timestamp=now.isoformat()),
        ]
        result = proj.project(events)
        rel_items = [i for i in result.items if i.reminder_type == ReminderType.RELATIONSHIP]
        assert len(rel_items) == 0


class TestEmotionReminder:
    def test_sustained_negative(self, proj):
        now = datetime.now(timezone.utc)
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        for i in range(5):
            events.append(create_event(type=EventType.EMOTION,
                                        data={"valence": -0.5, "label": "焦虑"},
                                        person="小雨",
                                        timestamp=(now - timedelta(days=i)).isoformat()))
        result = proj.project(events)
        emo_items = [i for i in result.items if i.reminder_type == ReminderType.EMOTION]
        assert len(emo_items) == 1
        assert emo_items[0].urgency == Urgency.HIGH

    def test_no_emotion_alert(self, proj):
        now = datetime.now(timezone.utc)
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        for i in range(5):
            events.append(create_event(type=EventType.EMOTION,
                                        data={"valence": 0.5, "label": "开心"},
                                        person="小雨",
                                        timestamp=(now - timedelta(days=i)).isoformat()))
        result = proj.project(events)
        emo_items = [i for i in result.items if i.reminder_type == ReminderType.EMOTION]
        assert len(emo_items) == 0


class TestGrowthReminder:
    def test_growth_stagnant(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨"),
            create_event(type=EventType.GROWTH, data={"title": "学Python", "category": "skill", "impact_level": 5, "date": "2025-01"},
                         person="小雨", timestamp=(now - timedelta(days=100)).isoformat()),
        ]
        result = proj.project(events)
        growth_items = [i for i in result.items if i.reminder_type == ReminderType.GROWTH]
        assert len(growth_items) == 1


class TestCustomReminder:
    def test_custom_reminder(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨"),
            create_event(type=EventType.REMINDER, data={
                "message": "明天考试", "trigger_date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                "urgency": "high", "status": "pending",
            }, person="小雨"),
        ]
        result = proj.project(events)
        custom_items = [i for i in result.items if i.reminder_type == ReminderType.CUSTOM]
        assert len(custom_items) == 1
        assert custom_items[0].message == "明天考试"


class TestTrigger:
    def test_trigger_types(self):
        t1 = ReminderTrigger(type=TriggerType.DATE, date="2025-06-15")
        assert t1.to_dict() == {"type": "date", "date": "2025-06-15"}

        t2 = ReminderTrigger(type=TriggerType.INACTIVITY, days=45)
        assert t2.to_dict() == {"type": "inactivity", "days": 45}

        t3 = ReminderTrigger(type=TriggerType.EMOTION, condition="negative_5_days")
        assert t3.to_dict() == {"type": "emotion", "condition": "negative_5_days"}


class TestStatus:
    def test_default_status(self, proj):
        now = datetime.now(timezone.utc)
        bd = now.strftime("%Y-%m-%d")
        events = [create_event(type=EventType.PERSON, data={"birthday": bd}, person="小雨")]
        result = proj.project(events)
        for item in result.items:
            assert item.status == ReminderStatus.PENDING


class TestSorting:
    def test_high_urgency_first(self, proj):
        now = datetime.now(timezone.utc)
        bd = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        events = [
            create_event(type=EventType.PERSON, data={"birthday": bd}, person="小雨"),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=8)).isoformat()),
        ]
        result = proj.project(events)
        if len(result.items) >= 2:
            # high 应该排在 medium 前面
            urgency_order = {"high": 0, "medium": 1, "low": 2}
            assert urgency_order[result.items[0].urgency.value] <= urgency_order[result.items[1].urgency.value]


class TestMetadata:
    def test_metadata(self, proj):
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        result = proj.project(events)
        assert "generated_at" in result.metadata
        assert "source_event_count" in result.metadata


class TestDataclassOutput:
    def test_to_dict(self, proj):
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        result = proj.project(events)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["items"], list)
