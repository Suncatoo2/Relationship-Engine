"""Tests for projections/emotion.py"""

import pytest
from datetime import datetime, timezone, timedelta
from src.event_types import EventType, create_event
from src.projections.emotion import (
    EmotionProjection, EmotionProfile, EmotionSnapshot,
    EmotionTrend, AlertRule, EmotionAlert, EmotionSummary,
    DEFAULT_ALERT_RULES,
)


@pytest.fixture
def proj():
    return EmotionProjection()


def make_emotion_events(now=None):
    now = now or datetime.now(timezone.utc)
    return [
        create_event(type=EventType.EMOTION, data={"valence": 0.8, "arousal": 0.6, "label": "开心", "context": "收到礼物"},
                     person="小雨", timestamp=(now - timedelta(days=10)).isoformat()),
        create_event(type=EventType.EMOTION, data={"valence": 0.5, "arousal": 0.4, "label": "平静", "context": "日常"},
                     person="小雨", timestamp=(now - timedelta(days=7)).isoformat()),
        create_event(type=EventType.EMOTION, data={"valence": -0.3, "arousal": 0.7, "label": "焦虑", "context": "考试"},
                     person="小雨", timestamp=(now - timedelta(days=4)).isoformat()),
        create_event(type=EventType.EMOTION, data={"valence": -0.6, "arousal": 0.8, "label": "焦虑", "context": "考砸了"},
                     person="小雨", timestamp=(now - timedelta(days=2)).isoformat()),
        create_event(type=EventType.EMOTION, data={"valence": 0.2, "arousal": 0.3, "label": "平静", "context": "考完了"},
                     person="小雨", timestamp=(now - timedelta(days=1)).isoformat()),
    ]


class TestEmpty:
    def test_empty(self, proj):
        assert proj.project([]) == {}

    def test_no_emotion_events(self, proj):
        events = [create_event(type=EventType.CHAT, data={}, person="小雨")]
        assert proj.project(events) == {}


class TestCurrent:
    def test_current_is_latest(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        p = result["小雨"]
        assert p.current is not None
        assert p.current.valence == 0.2
        assert p.current.label == "平静"


class TestHistory:
    def test_history_count(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        assert len(result["小雨"].history) == 5

    def test_history_sorted(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        timestamps = [h.timestamp for h in result["小雨"].history]
        assert timestamps == sorted(timestamps)


class TestTrend:
    def test_trend_enum(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        assert isinstance(result["小雨"].trend, EmotionTrend)

    def test_trend_declining(self, proj):
        """最近情绪下降"""
        now = datetime.now(timezone.utc)
        events = [
            # 前14-7天：正面
            create_event(type=EventType.EMOTION, data={"valence": 0.8, "label": "开心"}, person="小雨",
                         timestamp=(now - timedelta(days=14)).isoformat()),
            create_event(type=EventType.EMOTION, data={"valence": 0.7, "label": "开心"}, person="小雨",
                         timestamp=(now - timedelta(days=12)).isoformat()),
            create_event(type=EventType.EMOTION, data={"valence": 0.6, "label": "开心"}, person="小雨",
                         timestamp=(now - timedelta(days=10)).isoformat()),
            # 最近7天：负面
            create_event(type=EventType.EMOTION, data={"valence": -0.5, "label": "焦虑"}, person="小雨",
                         timestamp=(now - timedelta(days=3)).isoformat()),
            create_event(type=EventType.EMOTION, data={"valence": -0.6, "label": "焦虑"}, person="小雨",
                         timestamp=(now - timedelta(days=1)).isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].trend == EmotionTrend.DECLINING

    def test_trend_improving(self, proj):
        now = datetime.now(timezone.utc)
        events = [
            # 前14-7天：负面（3个确保足够）
            create_event(type=EventType.EMOTION, data={"valence": -0.6, "label": "焦虑"}, person="小雨",
                         timestamp=(now - timedelta(days=13)).isoformat()),
            create_event(type=EventType.EMOTION, data={"valence": -0.5, "label": "焦虑"}, person="小雨",
                         timestamp=(now - timedelta(days=11)).isoformat()),
            create_event(type=EventType.EMOTION, data={"valence": -0.4, "label": "焦虑"}, person="小雨",
                         timestamp=(now - timedelta(days=9)).isoformat()),
            # 最近7天：正面
            create_event(type=EventType.EMOTION, data={"valence": 0.5, "label": "开心"}, person="小雨",
                         timestamp=(now - timedelta(days=3)).isoformat()),
            create_event(type=EventType.EMOTION, data={"valence": 0.6, "label": "开心"}, person="小雨",
                         timestamp=(now - timedelta(days=1)).isoformat()),
        ]
        result = proj.project(events)
        assert result["小雨"].trend == EmotionTrend.IMPROVING

    def test_trend_insufficient(self, proj):
        events = [
            create_event(type=EventType.EMOTION, data={"valence": 0.5, "label": "开心"}, person="小雨"),
        ]
        result = proj.project(events)
        assert result["小雨"].trend == EmotionTrend.INSUFFICIENT


class TestDominantEmotion:
    def test_dominant_emotion(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        # 最近30条中"焦虑"出现2次，"平静"2次，"开心"1次
        # 按时间顺序最后出现的"平静"和"焦虑"各2次
        dominant = result["小雨"].dominant_emotion
        assert dominant in ("焦虑", "平静")

    def test_dominant_all_same(self, proj):
        now = datetime.now(timezone.utc)
        events = []
        for i in range(10):
            events.append(create_event(type=EventType.EMOTION,
                                        data={"valence": 0.5, "label": "开心"},
                                        person="小雨",
                                        timestamp=(now - timedelta(days=i)).isoformat()))
        result = proj.project(events)
        assert result["小雨"].dominant_emotion == "开心"


class TestAlerts:
    def test_alert_triggered(self, proj):
        now = datetime.now(timezone.utc)
        events = []
        for i in range(6):
            events.append(create_event(type=EventType.EMOTION,
                                        data={"valence": -0.5, "label": "焦虑"},
                                        person="小雨",
                                        timestamp=(now - timedelta(days=i)).isoformat()))
        result = proj.project(events)
        alerts = result["小雨"].alerts
        # 应该触发 5天 < -0.3 的规则
        assert len(alerts) > 0
        assert any(a.severity == "medium" for a in alerts)

    def test_alert_not_triggered(self, proj):
        now = datetime.now(timezone.utc)
        events = []
        for i in range(6):
            events.append(create_event(type=EventType.EMOTION,
                                        data={"valence": 0.5, "label": "开心"},
                                        person="小雨",
                                        timestamp=(now - timedelta(days=i)).isoformat()))
        result = proj.project(events)
        assert len(result["小雨"].alerts) == 0

    def test_custom_alert_rules(self):
        rules = [AlertRule(threshold=-0.8, window_days=1, severity="high")]
        proj = EmotionProjection(alert_rules=rules)
        now = datetime.now(timezone.utc)
        events = [
            create_event(type=EventType.EMOTION, data={"valence": -0.9, "label": "绝望"},
                         person="小雨", timestamp=now.isoformat()),
        ]
        result = proj.project(events)
        assert len(result["小雨"].alerts) == 1


class TestSummary:
    def test_summary_exists(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        s = result["小雨"].summary
        assert s is not None
        assert isinstance(s, EmotionSummary)
        assert -1 <= s.avg_valence <= 1
        assert 0 <= s.positive_ratio <= 1
        assert s.total_records == 5

    def test_summary_dominant_label(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        assert result["小雨"].summary.dominant_label


class TestMetadata:
    def test_metadata(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        m = result["小雨"].metadata
        assert "generated_at" in m
        assert "source_event_count" in m
        assert m["source_event_count"] == 5


class TestMomentumField:
    def test_momentum_none_by_default(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        assert result["小雨"].momentum is None


class TestDataclassOutput:
    def test_output_is_profile(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        assert isinstance(result["小雨"], EmotionProfile)

    def test_to_dict(self, proj):
        events = make_emotion_events()
        result = proj.project(events)
        d = result["小雨"].to_dict()
        assert isinstance(d, dict)
        assert d["trend"] in ("improving", "stable", "declining", "insufficient")
        assert isinstance(d["alerts"], list)
        assert isinstance(d["history"], list)


class TestProjectOne:
    def test_project_one(self, proj):
        events = make_emotion_events()
        p = proj.project_one(events, "小雨")
        assert p is not None
        assert p.current is not None

    def test_project_one_not_found(self, proj):
        assert proj.project_one([], "不存在") is None
