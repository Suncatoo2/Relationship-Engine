"""Emotion Projection — 情绪摘要投影

从 emotion 事件重建情绪状态。
只做 Replay + 统计 + 趋势，绝不推断情绪。
情绪识别是调用方 AI 的工作，Projection 只计算事实。

输入事件类型：
  - emotion: valence, arousal, label, context, timestamp

输出：dict[str, EmotionProfile]
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import Counter
from enum import Enum

from ..event_types import Event, EventType
from .base import Projection


# ---- 枚举 ----

class EmotionTrend(str, Enum):
    """情绪趋势枚举"""
    IMPROVING = "improving"   # 好转
    STABLE = "stable"         # 稳定
    DECLINING = "declining"   # 恶化
    INSUFFICIENT = "insufficient"  # 数据不足


# ---- 数据结构 ----

@dataclass
class EmotionSnapshot:
    """一条情绪快照"""
    valence: float          # -1.0 ~ +1.0
    arousal: float          # 0 ~ 1
    label: str
    context: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "label": self.label,
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class AlertRule:
    """报警规则"""
    threshold: float        # valence 阈值（低于此值触发）
    window_days: int        # 连续天数
    severity: str           # "low" / "medium" / "high"

    def to_dict(self) -> dict:
        return {
            "threshold": self.threshold,
            "window_days": self.window_days,
            "severity": self.severity,
        }


@dataclass
class EmotionAlert:
    """一条报警"""
    rule: AlertRule
    message: str
    severity: str
    days: int

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "severity": self.severity,
            "days": self.days,
            "rule": self.rule.to_dict(),
        }


@dataclass
class EmotionSummary:
    """情绪统计摘要"""
    avg_valence: float
    avg_arousal: float
    dominant_label: str
    positive_ratio: float
    total_records: int
    period_days: int

    def to_dict(self) -> dict:
        return {
            "avg_valence": round(self.avg_valence, 2),
            "avg_arousal": round(self.avg_arousal, 2),
            "dominant_label": self.dominant_label,
            "positive_ratio": round(self.positive_ratio, 2),
            "total_records": self.total_records,
            "period_days": self.period_days,
        }


@dataclass
class EmotionProfile:
    """情绪状态"""
    person_name: str
    current: EmotionSnapshot | None = None
    trend: EmotionTrend = EmotionTrend.INSUFFICIENT
    trend_detail: str = ""
    dominant_emotion: str = ""
    alerts: list[EmotionAlert] = field(default_factory=list)
    history: list[EmotionSnapshot] = field(default_factory=list)
    summary: EmotionSummary | None = None
    momentum: dict | None = None  # v3 扩展接口
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "current": self.current.to_dict() if self.current else None,
            "trend": self.trend.value,
            "trend_detail": self.trend_detail,
            "dominant_emotion": self.dominant_emotion,
            "alerts": [a.to_dict() for a in self.alerts],
            "history": [h.to_dict() for h in self.history],
            "summary": self.summary.to_dict() if self.summary else None,
            "momentum": self.momentum,
            "metadata": self.metadata,
        }


# ---- 默认报警规则 ----

DEFAULT_ALERT_RULES = [
    AlertRule(threshold=-0.3, window_days=5, severity="medium"),
    AlertRule(threshold=-0.5, window_days=3, severity="high"),
    AlertRule(threshold=-0.7, window_days=2, severity="high"),
]


# ---- Projection ----

class EmotionProjection(Projection):
    """情绪摘要投影

    只做 Replay + 统计 + 趋势。
    绝不推断情绪（情绪识别是调用方 AI 的工作）。
    """

    def __init__(self, alert_rules: list[AlertRule] | None = None):
        self.alert_rules = alert_rules or DEFAULT_ALERT_RULES

    def project(self, events) -> dict[str, EmotionProfile]:
        profiles: dict[str, EmotionProfile] = {}
        event_list = list(events)

        # 按人物分组 emotion 事件
        by_person: dict[str, list[Event]] = {}
        for e in event_list:
            if e.type == EventType.EMOTION and e.person:
                by_person.setdefault(e.person, []).append(e)

        for name, emotion_events in by_person.items():
            profiles[name] = self._build_profile(name, emotion_events)

        return profiles

    def project_one(self, events, name: str) -> EmotionProfile | None:
        return self.project(events).get(name)

    def _build_profile(self, name: str, events: list[Event]) -> EmotionProfile:
        p = EmotionProfile(person_name=name)
        now = datetime.now(timezone.utc)

        # 解析所有 emotion 事件为快照
        snapshots = []
        for e in events:
            snapshots.append(EmotionSnapshot(
                valence=e.data.get("valence", 0.0),
                arousal=e.data.get("arousal", 0.5),
                label=e.data.get("label", ""),
                context=e.data.get("context", ""),
                timestamp=e.timestamp,
            ))

        # 按时间排序
        snapshots.sort(key=lambda s: s.timestamp)

        if not snapshots:
            p.metadata = self._meta(len(events))
            return p

        # 当前情绪
        p.current = snapshots[-1]

        # 历史记录（最近 30 条）
        p.history = snapshots[-30:]

        # 统计摘要（最近 30 天）
        p.summary = self._compute_summary(snapshots, now)

        # 主导情绪
        p.dominant_emotion = self._compute_dominant(snapshots)

        # 趋势
        p.trend, p.trend_detail = self._compute_trend(snapshots, now)

        # 报警
        p.alerts = self._compute_alerts(snapshots, now)

        # metadata
        p.metadata = self._meta(len(events))

        return p

    def _compute_summary(self, snapshots: list[EmotionSnapshot], now: datetime) -> EmotionSummary:
        """最近 30 天统计摘要"""
        cutoff = now - timedelta(days=30)
        recent = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    recent.append(s)
            except (ValueError, TypeError):
                recent.append(s)

        if not recent:
            recent = snapshots[-10:]  # fallback

        avg_v = sum(s.valence for s in recent) / len(recent)
        avg_a = sum(s.arousal for s in recent) / len(recent)
        positive = sum(1 for s in recent if s.valence > 0)
        dominant = Counter(s.label for s in recent).most_common(1)[0][0] if recent else ""

        days_span = 30
        if len(recent) >= 2:
            try:
                first = datetime.fromisoformat(recent[0].timestamp)
                last = datetime.fromisoformat(recent[-1].timestamp)
                if first.tzinfo is None:
                    first = first.replace(tzinfo=timezone.utc)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                days_span = max(1, (last - first).days)
            except (ValueError, TypeError):
                pass

        return EmotionSummary(
            avg_valence=avg_v,
            avg_arousal=avg_a,
            dominant_label=dominant,
            positive_ratio=positive / len(recent),
            total_records=len(recent),
            period_days=days_span,
        )

    def _compute_dominant(self, snapshots: list[EmotionSnapshot]) -> str:
        """最近 30 条中最常见的情绪"""
        if not snapshots:
            return ""
        recent = snapshots[-30:]
        labels = [s.label for s in recent if s.label]
        if not labels:
            return ""
        return Counter(labels).most_common(1)[0][0]

    def _compute_trend(self, snapshots: list[EmotionSnapshot], now: datetime) -> tuple[EmotionTrend, str]:
        """计算趋势：最近7天 vs 前7天"""
        cutoff_7d = now - timedelta(days=7)
        cutoff_14d = now - timedelta(days=14)

        recent_7d = []
        prev_7d = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff_7d:
                    recent_7d.append(s.valence)
                elif ts >= cutoff_14d:
                    prev_7d.append(s.valence)
            except (ValueError, TypeError):
                pass

        if len(recent_7d) < 2 or len(prev_7d) < 2:
            return EmotionTrend.INSUFFICIENT, "数据不足，无法判断趋势"

        avg_recent = sum(recent_7d) / len(recent_7d)
        avg_prev = sum(prev_7d) / len(prev_7d)
        diff = avg_recent - avg_prev

        detail = f"最近7天 valence 均值 {avg_recent:.2f}，前7天 {avg_prev:.2f}"

        if diff > 0.2:
            return EmotionTrend.IMPROVING, detail
        elif diff < -0.2:
            return EmotionTrend.DECLINING, detail
        else:
            return EmotionTrend.STABLE, detail

    def _compute_alerts(self, snapshots: list[EmotionSnapshot], now: datetime) -> list[EmotionAlert]:
        """根据规则检查报警"""
        alerts = []
        for rule in self.alert_rules:
            cutoff = now - timedelta(days=rule.window_days)
            recent = []
            for s in snapshots:
                try:
                    ts = datetime.fromisoformat(s.timestamp)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts >= cutoff:
                        recent.append(s.valence)
                except (ValueError, TypeError):
                    pass

            if len(recent) >= rule.window_days:
                if all(v < rule.threshold for v in recent[-rule.window_days:]):
                    alerts.append(EmotionAlert(
                        rule=rule,
                        message=f"连续{rule.window_days}天 valence < {rule.threshold}",
                        severity=rule.severity,
                        days=rule.window_days,
                    ))

        return alerts

    def _meta(self, event_count: int) -> dict:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_event_count": event_count,
            "version": "1.0",
        }
