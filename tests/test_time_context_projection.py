"""Tests for projections/time_context.py"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.time_context import (
    TimeContextProjection, TimeContextProfile,
    DensityInfo, PeriodDistribution, SilenceInfo, ActiveWindow, Landmark,
)


@pytest.fixture
def proj():
    return TimeContextProjection()


def make_events(now=None):
    now = now or datetime.now(timezone.utc)
    return [
        # 30天前认识
        create_event(type=EventType.PERSON, data={"action": "create"}, person="小雨",
                     timestamp=(now - timedelta(days=30)).isoformat()),
        # 20天前聊天
        create_event(type=EventType.CHAT, data={"content": "你好"}, person="小雨",
                     timestamp=(now - timedelta(days=20)).isoformat()),
        # 10天前聊天
        create_event(type=EventType.CHAT, data={"content": "在干嘛"}, person="小雨",
                     timestamp=(now - timedelta(days=10)).isoformat()),
        # 3天前聊天
        create_event(type=EventType.CHAT, data={"content": "吃饭了吗"}, person="小雨",
                     timestamp=(now - timedelta(days=3)).isoformat()),
        # 1天前聊天
        create_event(type=EventType.CHAT, data={"content": "晚安"}, person="小雨",
                     timestamp=(now - timedelta(days=1)).isoformat()),
    ]


class TestEmpty:
    def test_empty(self, proj):
        assert proj.project([]) == {}


class TestRelativeTime:
    def test_days_since_last_chat(self, proj):
        events = make_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.days_since_last_chat == 1

    def test_days_since_first_met(self, proj):
        events = make_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.days_since_first_met == 30

    def test_last_chat_label(self, proj):
        events = make_events()
        result = proj.project(events)
        assert result["小雨"].last_chat_label == "昨天"

    def test_first_met_label(self, proj):
        events = make_events()
        result = proj.project(events)
        assert result["小雨"].first_met_label == "最近一个月"


class TestDensity:
    def test_density_7d(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨"),
            # 过去7天内5条聊天
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=1)).isoformat()),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=2)).isoformat()),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=3)).isoformat()),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=5)).isoformat()),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=6)).isoformat()),
        ]
        result = proj.project(events)
        d7 = result["小雨"].density_7d
        assert d7 is not None
        assert d7.event_count == 5
        assert d7.daily_avg == pytest.approx(5 / 7, abs=0.1)

    def test_density_30d(self, proj):
        events = make_events()
        result = proj.project(events)
        d30 = result["小雨"].density_30d
        assert d30 is not None
        assert d30.event_count == 4  # 4条chat事件

    def test_density_label_dense(self, proj):
        now = datetime.now(timezone.utc)
        events = [create_event(type=EventType.PERSON, data={}, person="x")]
        for i in range(30):
            events.append(create_event(type=EventType.CHAT, data={}, person="x",
                                        timestamp=(now - timedelta(hours=i)).isoformat()))
        result = proj.project(events)
        assert result["x"].density_7d.label == "很密集"


class TestPeriod:
    def test_period_distribution(self, proj):
        now = datetime.now(timezone.utc)
        # 都在晚上聊天
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨"),
        ]
        for i in range(5):
            ts = now.replace(hour=22, minute=0) - timedelta(days=i)
            events.append(create_event(type=EventType.CHAT, data={}, person="小雨",
                                        timestamp=ts.isoformat()))
        result = proj.project(events)
        p = result["小雨"].period
        assert p is not None
        assert p.evening == 5
        assert p.dominant_period == "evening"

    def test_period_dominant_day_type(self, proj):
        now = datetime.now(timezone.utc)
        events = [create_event(type=EventType.PERSON, data={}, person="小雨")]
        # 周末聊天多
        for i in range(10):
            ts = now - timedelta(days=i * 2)
            events.append(create_event(type=EventType.CHAT, data={}, person="小雨",
                                        timestamp=ts.isoformat()))
        result = proj.project(events)
        assert result["小雨"].period.dominant_day_type in ("weekday", "weekend")


class TestSilence:
    def test_silence_active(self, proj):
        events = make_events()
        result = proj.project(events)
        s = result["小雨"].silence
        assert s is not None
        assert s.status == "active"

    def test_silence_dormant(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨",
                         timestamp=(now - timedelta(days=100)).isoformat()),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=100)).isoformat()),
        ]
        result = proj.project(events)
        s = result["小雨"].silence
        assert s.status == "dormant"
        assert s.silence_days >= 100


class TestActiveWindow:
    def test_active_window(self, proj):
        events = make_events()
        result = proj.project(events)
        aw = result["小雨"].active_window
        assert aw is not None
        assert aw.total_days == 29  # 30天跨度 = 29天间隔
        assert aw.total_events == 5
        assert aw.label == "认识一个月" or aw.label == "认识不久"

    def test_active_window_new(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨",
                         timestamp=now.isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].active_window.total_days == 0


class TestLandmarks:
    def test_landmarks_generated(self, proj):
        now = datetime.now(timezone.utc)
        # 认识在 335 天前（30天后就是一周年）
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨",
                         timestamp=(now - timedelta(days=335)).isoformat()),
            create_event(type=EventType.CHAT, data={}, person="小雨",
                         timestamp=(now - timedelta(days=335)).isoformat()),
        ]
        result = proj.project(events)
        landmarks = result["小雨"].landmarks
        assert len(landmarks) > 0
        names = [l.name for l in landmarks]
        assert any("周年" in n for n in names)

    def test_landmarks_100_days(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.PERSON, data={}, person="小雨",
                         timestamp=(now - timedelta(days=80)).isoformat()),
        ]
        result = proj.project(events)
        landmarks = result["小雨"].landmarks
        names = [l.name for l in landmarks]
        assert "认识第100天" in names


class TestMetadata:
    def test_metadata(self, proj):
        events = make_events()
        result = proj.project(events)
        m = result["小雨"].metadata
        assert "generated_at" in m
        assert "source_event_count" in m
        assert m["source_event_count"] == 5


class TestDataclassOutput:
    def test_output_is_profile(self, proj):
        events = make_events()
        result = proj.project(events)
        assert isinstance(result["小雨"], TimeContextProfile)

    def test_to_dict(self, proj):
        events = make_events()
        result = proj.project(events)
        d = result["小雨"].to_dict()
        assert isinstance(d, dict)
        assert "days_since_last_chat" in d
        assert "silence" in d
        assert "active_window" in d


class TestProjectOne:
    def test_project_one(self, proj):
        events = make_events()
        p = proj.project_one(events, "小雨")
        assert p is not None
        assert p.days_since_last_chat == 1

    def test_project_one_not_found(self, proj):
        assert proj.project_one([], "不存在") is None
