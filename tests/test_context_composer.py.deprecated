"""Tests for projections/context.py (Context Composer)"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.context import ContextComposer, ContextSnapshot, DEFAULT_BUDGET_LIMIT


@pytest.fixture
def composer():
    return ContextComposer()


def make_full_events(now=None):
    now = now or datetime.now(timezone.utc)
    return [
        # 人物
        create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1998-06-15", "tags": ["暧昧"]},
                     person="小雨", occurred_at=(now - timedelta(days=30)).isoformat()),
        # 记忆
        create_event(type=EventType.FACT, data={"content": "喜欢奶茶", "category": "preference"},
                     person="小雨", occurred_at=(now - timedelta(days=25)).isoformat()),
        # 聊天
        create_event(type=EventType.CHAT, data={"role": "user", "content": "你好", "topics": ["问候"]},
                     person="小雨", occurred_at=(now - timedelta(days=5)).isoformat()),
        create_event(type=EventType.CHAT, data={"role": "assistant", "content": "你好呀"},
                     person="小雨", occurred_at=(now - timedelta(days=5, hours=-1)).isoformat()),
        # 关系
        create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 20, "event": "第一次约会"},
                     person="小雨", occurred_at=(now - timedelta(days=10)).isoformat()),
        # 情绪
        create_event(type=EventType.EMOTION, data={"valence": 0.8, "label": "开心"},
                     person="小雨", occurred_at=(now - timedelta(days=3)).isoformat()),
        # 成长
        create_event(type=EventType.GROWTH, data={"title": "学会Python", "category": "skill", "impact_level": 7, "date": "2026-01"},
                     person="小雨", occurred_at=(now - timedelta(days=20)).isoformat()),
    ]


class TestCompose:
    def test_compose_returns_snapshot(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert isinstance(snapshot, ContextSnapshot)

    def test_compose_has_person(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.person is not None
        assert snapshot.person.name == "小雨"

    def test_compose_has_relationship(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.relationship is not None

    def test_compose_has_time(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.time is not None

    def test_compose_has_emotion(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.emotion is not None

    def test_compose_has_growth(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.growth is not None

    def test_compose_has_conversation(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.conversation is not None

    def test_compose_has_reminder(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.reminder is not None


class TestBudget:
    def test_budget_with_small_limit(self):
        composer = ContextComposer(budget_limit=500)
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        # 应该有 excluded 的 Profile
        assert len(snapshot.excluded) > 0

    def test_budget_with_large_limit(self):
        composer = ContextComposer(budget_limit=50000)
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert len(snapshot.excluded) == 0

    def test_budget_high_priority_included(self):
        composer = ContextComposer(budget_limit=1500)
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        # HIGH 优先级的应该优先包含
        assert snapshot.relationship is not None or snapshot.reminder is not None

    def test_token_used_in_metadata(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert "token_used" in snapshot.metadata
        assert snapshot.metadata["token_used"] > 0


class TestMetadata:
    def test_metadata_fields(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        m = snapshot.metadata
        assert m["version"] == 1
        assert m["person_name"] == "小雨"
        assert m["budget_limit"] == DEFAULT_BUDGET_LIMIT
        assert m["event_count"] == 7
        assert "generated_at" in m
        assert "projection_versions" in m


class TestToDict:
    def test_to_dict(self, composer):
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        d = snapshot.to_dict()
        assert isinstance(d, dict)
        assert d["version"] == 1
        assert "person" in d
        assert "metadata" in d


class TestWithEventList:
    def test_compose_with_event_list(self, composer):
        """compose() 接受 list[Event]（Pipeline 标准路径）"""
        events = make_full_events()
        snapshot = composer.compose(events, "小雨")
        assert snapshot.person is not None


class TestEmptyEvents:
    def test_compose_empty(self, composer):
        snapshot = composer.compose([], "不存在")
        assert snapshot.person is None
        assert snapshot.relationship is None
        assert snapshot.metadata["event_count"] == 0
