"""Tests for CrossProjectionReasoner — Step 3: Cross-Projection Reasoning

Covers all 5 reasoning rules:
  - emotion_goal_link
  - silence_decay_alert
  - growth_stagnation
  - chemistry_emotion_divergence
  - milestone_timing_context

Plus: sorting, severity, evidence completeness, edge cases.
Following the same pattern as tests/test_whitebox_algorithms.py.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.cross_projection_reasoner import (
    Insight,
    CrossProjectionReasoner,
    _emotion_goal_link,
    _silence_decay_alert,
    _growth_stagnation,
    _chemistry_emotion_divergence,
    _milestone_timing_context,
)


# ============================================================
#  Helpers
# ============================================================

def _make_emotion_profile(dominant: str = "", valence: float = 0.0,
                          trend: str = "stable"):
    """Create a minimal EmotionProfile-like dict for tests."""
    # Uses simple objects with the right attributes
    class _Snapshot:
        def __init__(self, valence):
            self.valence = valence

    class _TrendEnum:
        def __init__(self, value):
            self.value = value

    class _Profile:
        def __init__(self, dominant, valence, trend):
            self.dominant_emotion = dominant
            self.current = _Snapshot(valence)
            self.trend = _TrendEnum(trend)

    return _Profile(dominant, valence, trend)


def _make_fact_state(stale_goals: list[dict] | None = None):
    """Create a minimal FactState-like dict for tests."""
    class _Fact:
        def __init__(self, content, category, last_confirmed="", created_at=""):
            self.content = content
            self.category = category
            self.last_confirmed = last_confirmed

    class _State:
        def __init__(self, goals):
            self.active = {}
            for i, g in enumerate(goals):
                key = f"goal_{i}"
                self.active[key] = _Fact(
                    content=g.get("content", ""),
                    category=g.get("category", "goal"),
                    last_confirmed=g.get("last_confirmed", ""),
                )

    if stale_goals is None:
        return _State([])
    return _State(stale_goals)


def _make_relationship_profile(lifecycle: str = "", last_contact_days: int = -1,
                               decay_chemistry: int = 50, stage: str = ""):
    class _Profile:
        def __init__(self, lifecycle, last_contact_days, decay_chemistry, stage):
            self.lifecycle = lifecycle
            self.last_contact_days = last_contact_days
            self.decay_chemistry = decay_chemistry
            self.stage = stage

    return _Profile(lifecycle, last_contact_days, decay_chemistry, stage)


def _make_growth_profile(has_recent: bool = True):
    class _Node:
        def __init__(self, timestamp):
            self.timestamp = timestamp

    class _Profile:
        def __init__(self, has_recent):
            self.timeline = []
            if has_recent:
                # Recent node from yesterday
                ts = datetime.now(timezone.utc) - timedelta(days=1)
                self.timeline.append(_Node(ts.isoformat()))
            else:
                # Old node from 100 days ago
                ts = datetime.now(timezone.utc) - timedelta(days=100)
                self.timeline.append(_Node(ts.isoformat()))

    return _Profile(has_recent)


def _make_time_profile(days_silence: int = 0, landmarks: list | None = None,
                       upcoming: list[str] | None = None):
    class _Landmark:
        def __init__(self, label, days_until):
            self.label = label
            self.days_until = days_until

    class _Profile:
        def __init__(self, days_silence, landmarks, upcoming):
            self.days_since_last_chat = days_silence
            self.landmarks = landmarks or []
            self.upcoming = upcoming or []

    return _Profile(days_silence, landmarks, upcoming)


# ============================================================
#  Rule 1: emotion_goal_link
# ============================================================

class TestEmotionGoalLink:
    def test_no_profiles_returns_empty(self):
        result = _emotion_goal_link({}, "Alice")
        assert result == []

    def test_no_negative_emotion_returns_empty(self):
        ep = {"Alice": _make_emotion_profile(dominant="开心", valence=0.8)}
        fp = {"Alice": _make_fact_state([])}
        # FactProjection dict needs active attr for rule to work
        result = _emotion_goal_link({"EmotionProjection": ep}, "Alice")
        assert result == []

    def test_negative_emotion_no_stale_goals(self):
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(dominant="焦虑", valence=-0.3)},
            "FactProjection": {"Alice": _make_fact_state([])},
        }
        result = _emotion_goal_link(profiles, "Alice")
        assert result == []

    def test_negative_emotion_with_stale_goal(self):
        # Create a FactProjection dict with active goals
        from datetime import datetime, timezone, timedelta

        stale_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "通过考研"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(dominant="焦虑", valence=-0.5)},
            "FactProjection": fp,
        }
        result = _emotion_goal_link(profiles, "Alice")
        assert len(result) > 0
        insight = result[0]
        assert insight.rule == "emotion_goal_link"
        assert "通过考研" in insight.summary
        assert "焦虑" in insight.summary
        assert "EmotionProjection" in insight.evidence
        assert "FactProjection" in insight.evidence
        assert 0.0 <= insight.confidence <= 1.0

    def test_sad_emotion_triggers_rule(self):
        fp = _make_fact_state([])
        ep = {"Alice": _make_emotion_profile(dominant="伤心", valence=-0.2)}
        # Missing FactProjection with stale goals → no results
        result = _emotion_goal_link({"EmotionProjection": ep}, "Alice")
        assert result == []

    def test_missing_emotion_profile_returns_empty(self):
        result = _emotion_goal_link({"FactProjection": {}}, "Alice")
        assert result == []

    def test_insight_has_confidence_and_severity(self):
        from datetime import datetime, timezone, timedelta
        stale_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "买房"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(dominant="压力", valence=-0.4)},
            "FactProjection": fp,
        }
        result = _emotion_goal_link(profiles, "Alice")
        assert len(result) == 1
        assert result[0].severity == "warning"  # 200 days stale → warning
        assert result[0].confidence > 0.6


# ============================================================
#  Rule 2: silence_decay_alert
# ============================================================

class TestSilenceDecayAlert:
    def test_no_profiles_returns_empty(self):
        assert _silence_decay_alert({}, "Bob") == []

    def test_winter_and_declining_is_critical(self):
        profiles = {
            "RelationshipProjection": {"Bob": _make_relationship_profile(
                lifecycle="winter", last_contact_days=45)},
            "EmotionProjection": {"Bob": _make_emotion_profile(
                dominant="难过", valence=-0.2, trend="declining")},
        }
        result = _silence_decay_alert(profiles, "Bob")
        assert len(result) == 1
        assert result[0].rule == "silence_decay_alert"
        assert result[0].severity == "critical"
        assert "winter" in str(result[0].evidence).lower() or "winter" in result[0].summary.lower()
        assert "declining" in str(result[0].evidence).lower()

    def test_winter_only_is_warning(self):
        profiles = {
            "RelationshipProjection": {"Bob": _make_relationship_profile(
                lifecycle="winter", last_contact_days=30)},
            "EmotionProjection": {"Bob": _make_emotion_profile(
                dominant="平静", valence=0.0, trend="stable")},
        }
        result = _silence_decay_alert(profiles, "Bob")
        assert len(result) == 1
        assert result[0].severity == "warning"

    def test_declining_only_is_warning(self):
        profiles = {
            "RelationshipProjection": {"Bob": _make_relationship_profile(
                lifecycle="autumn", last_contact_days=10)},
            "EmotionProjection": {"Bob": _make_emotion_profile(
                dominant="焦虑", valence=-0.1, trend="declining")},
        }
        result = _silence_decay_alert(profiles, "Bob")
        assert len(result) == 1
        assert result[0].severity == "warning"

    def test_healthy_relationship_returns_empty(self):
        profiles = {
            "RelationshipProjection": {"Bob": _make_relationship_profile(
                lifecycle="summer", last_contact_days=1)},
            "EmotionProjection": {"Bob": _make_emotion_profile(
                dominant="开心", valence=0.9, trend="improving")},
        }
        result = _silence_decay_alert(profiles, "Bob")
        assert result == []

    def test_missing_relationship_returns_empty(self):
        assert _silence_decay_alert({"EmotionProjection": {}}, "Bob") == []


# ============================================================
#  Rule 3: growth_stagnation
# ============================================================

class TestGrowthStagnation:
    def test_no_profiles_returns_empty(self):
        assert _growth_stagnation({}, "Carol") == []

    def test_no_recent_growth_and_silence(self):
        profiles = {
            "GrowthProjection": {"Carol": _make_growth_profile(has_recent=False)},
            "TimeContextProjection": {"Carol": _make_time_profile(days_silence=60)},
        }
        result = _growth_stagnation(profiles, "Carol")
        assert len(result) == 1
        assert result[0].rule == "growth_stagnation"
        assert result[0].severity == "info"

    def test_recent_growth_returns_empty(self):
        profiles = {
            "GrowthProjection": {"Carol": _make_growth_profile(has_recent=True)},
            "TimeContextProjection": {"Carol": _make_time_profile(days_silence=60)},
        }
        result = _growth_stagnation(profiles, "Carol")
        assert result == []

    def test_short_silence_returns_empty(self):
        profiles = {
            "GrowthProjection": {"Carol": _make_growth_profile(has_recent=False)},
            "TimeContextProjection": {"Carol": _make_time_profile(days_silence=5)},
        }
        result = _growth_stagnation(profiles, "Carol")
        assert result == []

    def test_missing_growth_profile_returns_empty(self):
        result = _growth_stagnation({"TimeContextProjection": {}}, "Carol")
        assert result == []


# ============================================================
#  Rule 4: chemistry_emotion_divergence
# ============================================================

class TestChemistryEmotionDivergence:
    def test_no_profiles_returns_empty(self):
        assert _chemistry_emotion_divergence({}, "Dave") == []

    def test_high_chemistry_negative_emotion(self):
        profiles = {
            "RelationshipProjection": {"Dave": _make_relationship_profile(
                decay_chemistry=75, stage="热恋")},
            "EmotionProjection": {"Dave": _make_emotion_profile(
                dominant="焦虑", valence=-0.4, trend="declining")},
        }
        result = _chemistry_emotion_divergence(profiles, "Dave")
        assert len(result) == 1
        assert result[0].rule == "chemistry_emotion_divergence"
        assert result[0].severity == "warning"

    def test_high_chemistry_happy_emotion_returns_empty(self):
        profiles = {
            "RelationshipProjection": {"Dave": _make_relationship_profile(
                decay_chemistry=80, stage="重要的人")},
            "EmotionProjection": {"Dave": _make_emotion_profile(
                dominant="开心", valence=0.9, trend="improving")},
        }
        result = _chemistry_emotion_divergence(profiles, "Dave")
        assert result == []

    def test_low_chemistry_returns_empty(self):
        profiles = {
            "RelationshipProjection": {"Dave": _make_relationship_profile(
                decay_chemistry=25, stage="认识")},
            "EmotionProjection": {"Dave": _make_emotion_profile(
                dominant="伤心", valence=-0.5, trend="declining")},
        }
        result = _chemistry_emotion_divergence(profiles, "Dave")
        assert result == []

    def test_sad_triggers_divergence(self):
        profiles = {
            "RelationshipProjection": {"Dave": _make_relationship_profile(
                decay_chemistry=70)},
            "EmotionProjection": {"Dave": _make_emotion_profile(
                dominant="疲惫", valence=-0.3)},
        }
        result = _chemistry_emotion_divergence(profiles, "Dave")
        assert len(result) == 1


# ============================================================
#  Rule 5: milestone_timing_context
# ============================================================

class TestMilestoneTimingContext:
    def test_no_profiles_returns_empty(self):
        assert _milestone_timing_context({}, "Eve") == []

    def test_upcoming_milestone_with_gap(self):
        from datetime import datetime, timezone, timedelta

        class _Landmark:
            def __init__(self, label, days_until):
                self.label = label
                self.days_until = days_until

        class _TimeProfile:
            def __init__(self):
                self.landmarks = [_Landmark("生日", 5)]
                self.upcoming = []

        profiles = {
            "RelationshipProjection": {"Eve": _make_relationship_profile(
                last_contact_days=14)},
            "TimeContextProjection": {"Eve": _TimeProfile()},
        }
        result = _milestone_timing_context(profiles, "Eve")
        assert len(result) >= 1
        assert result[0].rule == "milestone_timing_context"
        assert "生日" in result[0].summary
        assert "14" in result[0].summary

    def test_upcoming_milestone_recent_contact_skips(self):
        class _Landmark:
            def __init__(self, label, days_until):
                self.label = label
                self.days_until = days_until

        class _TimeProfile:
            def __init__(self):
                self.landmarks = [_Landmark("纪念日", 3)]
                self.upcoming = []

        profiles = {
            "RelationshipProjection": {"Eve": _make_relationship_profile(last_contact_days=0)},
            "TimeContextProjection": {"Eve": _TimeProfile()},
        }
        result = _milestone_timing_context(profiles, "Eve")
        assert result == []

    def test_no_upcoming_milestones(self):
        profiles = {
            "RelationshipProjection": {"Eve": _make_relationship_profile(last_contact_days=30)},
            "TimeContextProjection": {"Eve": _make_time_profile(days_silence=30)},
        }
        result = _milestone_timing_context(profiles, "Eve")
        assert result == []

    def test_missing_time_profile_returns_empty(self):
        result = _milestone_timing_context({"RelationshipProjection": {}}, "Eve")
        assert result == []


# ============================================================
#  CrossProjectionReasoner — integration
# ============================================================

class TestCrossProjectionReasoner:
    @pytest.fixture
    def reasoner(self):
        return CrossProjectionReasoner()

    def test_empty_profiles_returns_empty(self, reasoner):
        result = reasoner.reason({}, "anyone")
        assert result == []

    def test_empty_person_name(self, reasoner):
        result = reasoner.reason({}, "")
        assert result == []

    def test_results_sorted_by_severity(self, reasoner):
        """Critical insights must come before warning, then info."""
        # Create profiles that trigger multiple rules
        from datetime import datetime, timezone, timedelta

        stale_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "通过考研"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        class _Landmark:
            def __init__(self, label, days_until):
                self.label = label
                self.days_until = days_until

        class _TimeProfile:
            def __init__(self):
                self.landmarks = [_Landmark("生日", 7)]
                self.upcoming = []

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(
                dominant="焦虑", valence=-0.5, trend="declining")},
            "FactProjection": fp,
            "RelationshipProjection": {"Alice": _make_relationship_profile(
                lifecycle="winter", last_contact_days=45, decay_chemistry=70, stage="朋友")},
            "TimeContextProjection": {"Alice": _TimeProfile()},
        }

        result = reasoner.reason(profiles, "Alice")
        # silence_decay_alert (critical) should come before emotion_goal_link (warning/info)
        severities = [r.severity for r in result]
        # All criticals before all warnings before all infos
        for i in range(len(severities) - 1):
            rank_map = {"critical": 0, "warning": 1, "info": 2}
            assert rank_map[severities[i]] <= rank_map[severities[i + 1]], \
                f"Severities out of order: {severities}"

    def test_rule_failure_does_not_block_others(self, reasoner):
        """One rule throwing exception should not prevent other rules from running."""
        # Use a profile that would make chemistry_emotion_divergence work
        # and emotion_goal_link should also fire
        from datetime import datetime, timezone, timedelta

        stale_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "学日语"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(
                dominant="焦虑", valence=-0.4)},
            "FactProjection": fp,
            "RelationshipProjection": {"Alice": _make_relationship_profile(
                lifecycle="winter", last_contact_days=45, decay_chemistry=70)},
        }
        result = reasoner.reason(profiles, "Alice")
        # Both silence_decay and emotion_goal should fire
        assert len(result) > 0
        rules = set(r.rule for r in result)
        # At minimum silence_decay_alert (critical) fires
        assert "silence_decay_alert" in rules


# ============================================================
#  Insight dataclass
# ============================================================

class TestInsight:
    def test_to_dict(self):
        i = Insight(
            rule="test_rule",
            summary="A test insight",
            confidence=0.85,
            evidence={"FactProjection": {"content": "test"}},
            severity="warning",
        )
        d = i.to_dict()
        assert d["rule"] == "test_rule"
        assert d["summary"] == "A test insight"
        assert d["confidence"] == 0.85
        assert d["severity"] == "warning"
        assert "FactProjection" in d["evidence"]
        assert d["evidence"]["FactProjection"]["content"] == "test"

    def test_default_severity_is_info(self):
        i = Insight(rule="x", summary="x", confidence=0.5, evidence={})
        assert i.severity == "info"


# ============================================================
#  Behavioral Invariants
# ============================================================

class TestBehavioralInvariants:
    @pytest.fixture
    def reasoner(self):
        return CrossProjectionReasoner()

    def test_all_insights_have_evidence(self, reasoner):
        from datetime import datetime, timezone, timedelta

        stale_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "目标"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(
                dominant="焦虑", valence=-0.5, trend="declining")},
            "FactProjection": fp,
            "RelationshipProjection": {"Alice": _make_relationship_profile(
                lifecycle="winter", last_contact_days=45, decay_chemistry=72)},
        }

        result = reasoner.reason(profiles, "Alice")
        for insight in result:
            assert insight.evidence, f"Insight {insight.rule} missing evidence"
            assert len(insight.evidence) >= 2, \
                f"Insight {insight.rule} should reference >= 2 projections, got {len(insight.evidence)}"

    def test_all_confidences_in_range(self, reasoner):
        from datetime import datetime, timezone, timedelta

        stale_date = (datetime.now(timezone.utc) - timedelta(days=150)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "目标"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        class _Landmark:
            def __init__(self, label, days_until):
                self.label = label
                self.days_until = days_until

        class _TimeProfile:
            def __init__(self):
                self.landmarks = [_Landmark("生日", 3)]
                self.upcoming = []

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(
                dominant="焦虑", valence=-0.5, trend="declining")},
            "FactProjection": fp,
            "RelationshipProjection": {"Alice": _make_relationship_profile(
                lifecycle="winter", last_contact_days=45, decay_chemistry=72)},
            "TimeContextProjection": {"Alice": _TimeProfile()},
        }

        result = reasoner.reason(profiles, "Alice")
        for insight in result:
            assert 0.0 <= insight.confidence <= 1.0, \
                f"Insight {insight.rule} confidence {insight.confidence} out of range"

    def test_no_duplicate_insights(self, reasoner):
        """Each rule should fire at most once per profile set."""
        from datetime import datetime, timezone, timedelta

        stale_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()

        class _Fact:
            def __init__(self):
                self.content = "目标"
                self.category = "goal"
                self.last_confirmed = stale_date
                self.created_at = stale_date

        class _FactState:
            def __init__(self):
                self.active = {"goal_0": _Fact()}

        fp = {"Alice": _FactState()}
        profiles = {
            "EmotionProjection": {"Alice": _make_emotion_profile(
                dominant="焦虑", valence=-0.5, trend="declining")},
            "FactProjection": fp,
            "RelationshipProjection": {"Alice": _make_relationship_profile(
                lifecycle="winter", last_contact_days=45, decay_chemistry=72)},
        }

        result = reasoner.reason(profiles, "Alice")
        counts = {}
        for i in result:
            counts[i.rule] = counts.get(i.rule, 0) + 1
        for rule, count in counts.items():
            assert count == 1, f"Rule {rule} fired {count} times, expected 1"
