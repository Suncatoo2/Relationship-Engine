"""Cross-Projection Reasoner — discovers hidden relationships between Projections

ADR-007: Engine Detects, LLM Interprets.
This module discovers patterns across projections — it does NOT infer emotions,
intentions, or meaning. Every finding is backed by evidence from projection data.

Architecture:
  - Pure functions: no state, no I/O, no Pipeline access
  - Evidence-based: every Insight carries {projection_name: {field: value}}
  - Severity-graded: info → warning → critical
  - Deterministic: same input → same Insight list (no LLM, no randomness)
  - Extensible: new rule = new function + registration

Rules consume 2-3 projection snapshots and emit zero or more Insight objects.

This is the "Reasoning" layer — it connects dots between projections.
Not Compose (synthesizing blocks). Not Rank (selecting facts). Reason (connecting dots).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict


# ============================================================
#  Insight — the output type
# ============================================================

@dataclass
class Insight:
    """A single cross-projection discovery.

    Each Insight is backed by deterministic evidence from projection data.
    It is NOT an LLM inference — it's a pattern the Engine detected.
    """
    rule: str                    # e.g. "emotion_goal_link"
    summary: str                 # human-readable description
    confidence: float            # 0.0–1.0
    evidence: dict               # {projection_name: {field: value, ...}}
    severity: str = "info"       # info | warning | critical

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "summary": self.summary,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "severity": self.severity,
        }


# ============================================================
#  Reasoning Rules — pure functions
# ============================================================

def _get_now() -> datetime:
    return datetime.now(timezone.utc)


def _days_since(iso_str: str) -> int:
    """Parse an ISO timestamp and return days since now."""
    if not iso_str:
        return -1
    try:
        ts = datetime.fromisoformat(iso_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (_get_now() - ts).days
    except (ValueError, TypeError):
        return -1


# ---- Rule 1: emotion_goal_link ----

def _emotion_goal_link(profiles: dict, person: str) -> list[Insight]:
    """If dominant emotion is negative AND a goal is stale (>60 days),
    the goal may be contributing to the negative emotion.
    """
    ep = profiles.get("EmotionProjection")
    fp = profiles.get("FactProjection")

    if ep is None or fp is None:
        return []

    if not isinstance(ep, dict) or not isinstance(fp, dict):
        return []

    emo = ep.get(person)
    if emo is None or not hasattr(emo, "dominant_emotion"):
        return []

    dominant = emo.dominant_emotion if hasattr(emo, "dominant_emotion") else ""
    valence = emo.current.valence if hasattr(emo, "current") and emo.current else 0.0

    # Only trigger for negative emotions
    negative_set = {"焦虑", "伤心", "难过", "压力", "紧张", "疲惫", "困惑", "生气", "恐惧",
                    "anxious", "sad", "stressed", "tired", "angry", "fearful"}
    is_negative = (dominant in negative_set) or (isinstance(valence, (int, float)) and valence < -0.1)

    if not is_negative:
        return []

    # Find stale goals in FactProjection
    # fp is {person: FactState} — need the person's FactState
    fs = fp.get(person)
    if fs is None:
        return []

    stale_goals = []
    if hasattr(fs, "active"):
        for cat, f in fs.active.items():
            if cat == "goal" or (hasattr(f, "category") and getattr(f, "category", "") == "goal"):
                last_confirmed = getattr(f, "last_confirmed", "")
                created = getattr(f, "created_at", "")
                ref_date = last_confirmed or created
                if ref_date:
                    days = _days_since(ref_date)
                    if days > 60:
                        stale_goals.append({
                            "goal": getattr(f, "content", ""),
                            "days_stale": days,
                        })

    if not stale_goals:
        return []

    insights = []
    for g in stale_goals[:3]:  # top 3
        goal_content = g["goal"]
        days = g["days_stale"]
        confidence = min(0.85, 0.5 + (days - 60) * 0.005)  # increases with staleness

        insights.append(Insight(
            rule="emotion_goal_link",
            summary=f"{person if person else '用户'} 最近情绪 {dominant}，目标「{goal_content}」已 {days} 天未更新",
            confidence=round(confidence, 2),
            evidence={
                "EmotionProjection": {"dominant_emotion": dominant, "valence": valence},
                "FactProjection": {"goal": goal_content, "days_stale": days},
            },
            severity="warning" if days > 120 else "info",
        ))

    return insights


# ---- Rule 2: silence_decay_alert ----

def _silence_decay_alert(profiles: dict, person: str) -> list[Insight]:
    """Compound alert: lifecycle is 'winter' AND emotion trend is 'declining'.
    Two decaying signals reinforce each other.
    """
    rp = profiles.get("RelationshipProjection")
    ep = profiles.get("EmotionProjection")

    if rp is None or ep is None:
        return []

    if not isinstance(rp, dict) or not isinstance(ep, dict):
        return []

    rel = rp.get(person)
    emo = ep.get(person)
    if rel is None or emo is None:
        return []

    lifecycle = getattr(rel, "lifecycle", "")
    contact_days = getattr(rel, "last_contact_days", -1)
    emotion_trend = getattr(emo, "trend", None)
    trend_str = emotion_trend.value if hasattr(emotion_trend, "value") else str(emotion_trend or "")

    if lifecycle == "winter" and "declining" in trend_str:
        return [Insight(
            rule="silence_decay_alert",
            summary=f"关系进入冬季（{contact_days}天未联系），情绪也在下降，两者可能相互加速",
            confidence=0.82,
            evidence={
                "RelationshipProjection": {"lifecycle": lifecycle, "last_contact_days": contact_days},
                "EmotionProjection": {"trend": trend_str},
            },
            severity="critical",
        )]

    if lifecycle == "winter":
        return [Insight(
            rule="silence_decay_alert",
            summary=f"关系进入冬季，{contact_days}天未联系",
            confidence=0.70,
            evidence={"RelationshipProjection": {"lifecycle": lifecycle, "last_contact_days": contact_days}},
            severity="warning",
        )]

    if "declining" in trend_str:
        return [Insight(
            rule="silence_decay_alert",
            summary=f"情绪持续下降，建议关注原因",
            confidence=0.55,
            evidence={
                "EmotionProjection": {"trend": trend_str},
                "RelationshipProjection": {"lifecycle": lifecycle, "last_contact_days": contact_days},
            },
            severity="warning",
        )]

    return []


# ---- Rule 3: growth_stagnation ----

def _growth_stagnation(profiles: dict, person: str) -> list[Insight]:
    """No recent growth nodes AND significant silence → stagnation risk."""
    gp = profiles.get("GrowthProjection")
    tp = profiles.get("TimeContextProjection")

    if gp is None or tp is None:
        return []

    if not isinstance(gp, dict) or not isinstance(tp, dict):
        return []

    growth = gp.get(person)
    time_ctx = tp.get(person)

    days_silence = -1
    if time_ctx is not None and hasattr(time_ctx, "days_since_last_chat"):
        days_silence = getattr(time_ctx, "days_since_last_chat", -1)

    # Check growth recency
    recent_growth = False
    if growth is not None and hasattr(growth, "timeline"):
        for node in growth.timeline:
            ts = getattr(node, "timestamp", "")
            days = _days_since(ts)
            if 0 <= days <= 60:
                recent_growth = True
                break

    if growth is not None and not recent_growth and days_silence > 30:
        return [Insight(
            rule="growth_stagnation",
            summary=f"近60天没有新的成长记录，且已沉默{days_silence}天",
            confidence=0.45,
            evidence={
                "GrowthProjection": {"recent_growth": False},
                "TimeContextProjection": {"days_since_last_chat": days_silence},
            },
            severity="info",
        )]

    return []


# ---- Rule 4: chemistry_emotion_divergence ----

def _chemistry_emotion_divergence(profiles: dict, person: str) -> list[Insight]:
    """High relationship chemistry (>60) but dominant emotion is negative.
    Suggests surface-level relationship health masking internal struggle.
    """
    rp = profiles.get("RelationshipProjection")
    ep = profiles.get("EmotionProjection")

    if rp is None or ep is None:
        return []

    if not isinstance(rp, dict) or not isinstance(ep, dict):
        return []

    rel = rp.get(person)
    emo = ep.get(person)
    if rel is None or emo is None:
        return []

    chemistry = getattr(rel, "decay_chemistry", 0)
    stage = getattr(rel, "stage", "")
    dominant = emo.dominant_emotion if hasattr(emo, "dominant_emotion") else ""
    valence = emo.current.valence if hasattr(emo, "current") and emo.current else 0.0

    negative_set = {"焦虑", "伤心", "难过", "压力", "紧张", "疲惫", "困惑", "生气", "恐惧",
                    "anxious", "sad", "stressed", "tired", "angry", "fearful"}
    is_negative = dominant in negative_set or (isinstance(valence, (int, float)) and valence < -0.1)

    if chemistry > 60 and is_negative:
        return [Insight(
            rule="chemistry_emotion_divergence",
            summary=f"关系表面健康（好感度{chemistry}），但{person}最近情绪{dominant}，可能内心仍有 struggle",
            confidence=0.60,
            evidence={
                "RelationshipProjection": {"decay_chemistry": chemistry, "stage": stage},
                "EmotionProjection": {"dominant_emotion": dominant, "valence": valence},
            },
            severity="warning",
        )]

    return []


# ---- Rule 5: milestone_timing_context ----

def _milestone_timing_context(profiles: dict, person: str) -> list[Insight]:
    """Upcoming milestone AND last contact is distant → reminder value."""
    rp = profiles.get("RelationshipProjection")
    tp = profiles.get("TimeContextProjection")

    if rp is None or tp is None:
        return []

    if not isinstance(rp, dict) or not isinstance(tp, dict):
        return []

    rel = rp.get(person)
    time_ctx = tp.get(person)

    contact_days = getattr(rel, "last_contact_days", -1) if rel else -1

    upcoming = []
    if time_ctx is not None:
        # Try landmarks list
        if hasattr(time_ctx, "landmarks"):
            for lm in getattr(time_ctx, "landmarks", []):
                label = getattr(lm, "label", "")
                days_until = getattr(lm, "days_until", None)
                if label and days_until is not None and 0 < days_until <= 14:
                    upcoming.append({"label": label, "days_until": days_until})

        # Try upcoming list
        if hasattr(time_ctx, "upcoming"):
            up_list = getattr(time_ctx, "upcoming", [])
            for item in up_list:
                if isinstance(item, str) and item:
                    if not any(u["label"] == item for u in upcoming):
                        upcoming.append({"label": item, "days_until": None})

    # Skip person's own birthday check from TimeContext — we just care about
    # upcoming events + contact gap
    if not upcoming:
        return []

    insights = []
    for u in upcoming[:3]:
        label = u["label"]
        days_until = u.get("days_until")

        if contact_days > 7 or contact_days < 0:
            summary = f"即将到来的「{label}」，上次联系是{contact_days}天前"
            severity = "info"
        elif contact_days > 0:
            summary = f"即将到来的「{label}」，上次联系是{contact_days}天前——还来得及准备"
            severity = "info"
        else:
            continue  # already in contact, no insight needed

        insights.append(Insight(
            rule="milestone_timing_context",
            summary=summary,
            confidence=0.75 if days_until else 0.50,
            evidence={
                "TimeContextProjection": {"upcoming": label, "days_until": days_until},
                "RelationshipProjection": {"last_contact_days": contact_days},
            },
            severity=severity,
        ))

    return insights


# ============================================================
#  Rule Registry
# ============================================================

# Each rule is a (function, priority) pair.
# Priority determines sorting when multiple rules fire.
# Lower number = higher priority (inspected first).
_RULES: list[tuple] = [
    (_silence_decay_alert, 0),          # critical: compound decay
    (_chemistry_emotion_divergence, 1), # warning: surface vs inside
    (_emotion_goal_link, 2),            # warning/info: emotion ↔ goal
    (_milestone_timing_context, 3),     # info: milestone + contact gap
    (_growth_stagnation, 4),            # info: growth + silence
]

# Severity rank for sorting results
_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


class CrossProjectionReasoner:
    """Discovers hidden relationships between Projection snapshots.

    Usage:
        reasoner = CrossProjectionReasoner()
        insights = reasoner.reason(profiles, person="Alice")
        # Returns list[Insight], sorted by severity then confidence.
    """

    def __init__(self, rules: list[tuple] | None = None):
        self._rules = rules or _RULES

    def reason(self, profiles: dict[str, dict], person: str) -> list[Insight]:
        """Run all registered reasoning rules against the given profiles.

        Args:
            profiles: Dispatcher.project_all() output {ProjectionName: {person: profile}}
            person: person name to reason about

        Returns:
            list[Insight], sorted by severity (critical first) then confidence (highest first)
        """
        all_insights: list[Insight] = []

        for rule_fn, _priority in self._rules:
            try:
                results = rule_fn(profiles, person)
                all_insights.extend(results)
            except Exception:
                # One rule failing should not break other rules
                continue

        # Sort: severity (critical first), then confidence (highest first)
        all_insights.sort(key=lambda i: (
            _SEVERITY_RANK.get(i.severity, 99),
            -i.confidence,
        ))

        return all_insights
