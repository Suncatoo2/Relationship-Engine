"""Tests for projections/conversation.py (v2 — 分析模式)"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.conversation import (
    ConversationProjection, ConversationProfile, WindowStats,
)


@pytest.fixture
def proj():
    return ConversationProjection()


def make_chat_events(now=None):
    now = now or datetime.now(timezone.utc)
    return [
        create_event(type=EventType.PERSON, data={}, person="小雨",
                     timestamp=(now - timedelta(days=30)).isoformat()),
        # 30天前聊天
        create_event(type=EventType.CHAT, data={"role": "user", "content": "你好", "topics": ["问候"]}, person="小雨",
                     timestamp=(now - timedelta(days=30)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "你好呀"}, person="小雨",
                     timestamp=(now - timedelta(days=30, hours=-1)).isoformat()),
        # 20天前聊 Python
        create_event(type=EventType.CHAT, data={"role": "user", "content": "学Python", "topics": ["Python", "编程"]}, person="小雨",
                     timestamp=(now - timedelta(days=20)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "推荐教程"}, person="小雨",
                     timestamp=(now - timedelta(days=20, hours=-1)).isoformat()),
        # 5天前聊 CAD
        create_event(type=EventType.CHAT, data={"role": "user", "content": "CAD好难", "topics": ["CAD", "口腔"]}, person="小雨",
                     timestamp=(now - timedelta(days=5)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "多练习"}, person="小雨",
                     timestamp=(now - timedelta(days=5, hours=-1)).isoformat()),
        # 1天前聊 AI
        create_event(type=EventType.CHAT, data={"role": "user", "content": "AI真有意思", "topics": ["AI", "编程"]}, person="小雨",
                     timestamp=(now - timedelta(days=1)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "是的"}, person="小雨",
                     timestamp=(now - timedelta(days=1, hours=-1)).isoformat()),
        # 老王
        create_event(type=EventType.CHAT, data={"role": "user", "content": "天气不错", "topics": ["天气"]}, person="老王",
                     timestamp=(now - timedelta(days=3)).isoformat()),
    ]


class TestEmpty:
    def test_empty(self, proj):
        assert proj.project([]) == {}

    def test_no_chat_events(self, proj):
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        assert proj.project(events) == {}


class TestNoMessages:
    def test_no_messages_stored(self, proj):
        """Conversation 不保存聊天记录"""
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        # 不应该有 messages 字段
        assert not hasattr(p, "messages") or not isinstance(getattr(p, "messages", None), list)


class TestThreeLayerWindow:
    def test_all_time_exists(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.all_time is not None
        assert p.all_time.message_count == 8

    def test_recent_window(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.recent is not None
        assert p.recent.message_count <= 20

    def test_last_week_window(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.last_week is not None
        # 5天前和1天前的消息应该在 last_week 窗口
        assert p.last_week.message_count >= 4

    def test_window_stats_fields(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        w = result["小雨"].all_time
        assert w.user_count > 0
        assert w.assistant_count > 0
        assert w.messages_per_day > 0


class TestTopicFrequency:
    def test_topics_extracted(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert "编程" in p.topic_frequency
        assert p.topic_frequency["编程"] == 2  # Python + AI 都打了"编程"标签

    def test_top_topics(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert len(p.top_topics) > 0
        assert len(p.top_topics) <= 5

    def test_no_topics(self, proj):
        events = [
            create_event(type=EventType.CHAT, data={"role": "user", "content": "hi"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].topic_frequency == {}


class TestDensity:
    def test_dense(self, proj):
        now = datetime.now(timezone.utc)
        events = []
        # 10天内60条消息 → 6条/天 → dense
        for i in range(60):
            events.append(create_event(type=EventType.CHAT,
                                        data={"role": "user", "content": f"msg{i}"},
                                        person="小雨",
                                        timestamp=(now - timedelta(hours=i * 4)).isoformat()))
        result = proj.project(events)
        assert result["小雨"].conversation_density == "dense"

    def test_sparse(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.CHAT, data={"role": "user", "content": "hi"}, person="小雨",
                         timestamp=(now - timedelta(days=60)).isoformat()),
            create_event(type=EventType.CHAT, data={"role": "user", "content": "hi"}, person="小雨",
                         timestamp=(now - timedelta(days=30)).isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].conversation_density == "sparse"


class TestConfidence:
    def test_confidence_range(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        assert 0 <= result["小雨"].confidence <= 1

    def test_confidence_with_few_events(self, proj):
        events = [
            create_event(type=EventType.CHAT, data={"role": "user", "content": "hi"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].confidence < 0.5

    def test_confidence_with_many_events(self, proj):
        now = datetime.now(timezone.utc)
        events = []
        for i in range(100):
            events.append(create_event(type=EventType.CHAT,
                                        data={"role": "user", "content": f"msg{i}"},
                                        person="小雨",
                                        timestamp=(now - timedelta(days=i)).isoformat()))
        result = proj.project(events)
        assert result["小雨"].confidence > 0.5


class TestDerivedFrom:
    def test_derived_from(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        assert len(result["小雨"].derived_from) == 8
        # 每个 event_id 都应该记录


class TestTimeFields:
    def test_first_and_last_chat(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.first_chat
        assert p.last_chat
        assert p.first_chat < p.last_chat


class TestMetadata:
    def test_metadata(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        m = result["小雨"].metadata
        assert "generated_at" in m
        assert "source_event_count" in m


class TestDataclassOutput:
    def test_to_dict(self, proj):
        events = make_chat_events()
        result = proj.project(events)
        d = result["小雨"].to_dict()
        assert isinstance(d, dict)
        assert d["version"] == 1
        assert isinstance(d["topic_frequency"], dict)
        assert isinstance(d["top_topics"], list)
        assert isinstance(d["derived_from"], list)


class TestProjectOne:
    def test_project_one(self, proj):
        events = make_chat_events()
        p = proj.project_one(events, "小雨")
        assert p is not None
        assert p.all_time.message_count == 8

    def test_project_one_not_found(self, proj):
        assert proj.project_one([], "不存在") is None
