"""Tests for projections/conversation.py"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.conversation import (
    ConversationProjection, ConversationProfile, ChatMessage,
)


@pytest.fixture
def proj():
    return ConversationProjection()


def make_chat_events(now=None):
    now = now or datetime.now(timezone.utc)
    return [
        create_event(type=EventType.PERSON, data={}, person="小雨",
                     timestamp=(now - timedelta(days=10)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "user", "content": "你好"}, person="小雨",
                     timestamp=(now - timedelta(days=10)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "你好呀"}, person="小雨",
                     timestamp=(now - timedelta(days=10, hours=-1)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "user", "content": "在干嘛"}, person="小雨",
                     timestamp=(now - timedelta(days=5)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "在学习"}, person="小雨",
                     timestamp=(now - timedelta(days=5, hours=-1)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "user", "content": "吃饭了吗"}, person="小雨",
                     timestamp=(now - timedelta(days=1)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "吃了"}, person="小雨",
                     timestamp=(now - timedelta(days=1, hours=-1)).isoformat()),
        # 老王的消息
        create_event(type=EventType.CHAT, data={"role": "user", "content": "天气不错"}, person="老王",
                     timestamp=(now - timedelta(days=3)).isoformat()),
    ]


class TestEmpty:
    def test_empty(self, proj):
        assert proj.project([]) == {}

    def test_no_chat_events(self, proj):
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        assert proj.project(events) == {}


class TestBasicReplay:
    def test_message_count(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        assert result["小雨"].total_messages == 6
        assert result["老王"].total_messages == 1

    def test_recent_messages(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        assert len(result["小雨"].recent_messages) == 6

    def test_messages_sorted(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        timestamps = [m.timestamp for m in result["小雨"].recent_messages]
        assert timestamps == sorted(timestamps)

    def test_first_and_last_chat(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.first_chat
        assert p.last_chat
        assert p.first_chat < p.last_chat


class TestMessageContent:
    def test_message_roles(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        roles = [m.role for m in result["小雨"].recent_messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_message_content(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        contents = [m.content for m in result["小雨"].recent_messages]
        assert "你好" in contents
        assert "吃饭了吗" in contents


class TestRecentLimit:
    def test_recent_limit(self):
        proj = ConversationProjection(recent_limit=3)
        events = make_chat_events()
        result = proj.project(events)
        assert len(result["小雨"].recent_messages) == 3
        assert result["小雨"].total_messages == 6  # total 不变


class TestAvgPerDay:
    def test_avg_messages_per_day(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        assert result["小雨"].avg_messages_per_day > 0

    def test_single_message(self, proj):
        events = [
            create_event(type=EventType.CHAT, data={"role": "user", "content": "hi"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].avg_messages_per_day == 1.0


class TestMetadata:
    def test_metadata(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        m = result["小雨"].metadata
        assert "generated_at" in m
        assert "source_event_count" in m


class TestDataclassOutput:
    def test_output_is_profile(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        assert isinstance(result["小雨"], ConversationProfile)

    def test_to_dict(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        d = result["小雨"].to_dict()
        assert isinstance(d, dict)
        assert d["person_name"] == "小雨"
        assert isinstance(d["recent_messages"], list)
        assert d["version"] == 1


class TestProjectOne:
    def test_project_one(self, proj):
        events = make_chat_events()
        p = proj.project_one(events, "小雨")
        assert p is not None
        assert p.total_messages == 6

    def test_project_one_not_found(self, proj):
        assert proj.project_one([], "不存在") is None
