"""Conversation Projection — 对话分析投影

不保存聊天记录（Event Log 已经存了），只分析对话模式。
核心输出：话题频率、对话密度、三层窗口统计、沟通模式。

输入事件类型：
  - chat: role, content, topics（调用方 AI 打标签）, timestamp

输出：dict[str, ConversationProfile]

设计原则：
  - 不存 messages（Event Log 是数据库，Projection 不是）
  - topic_frequency 是核心输出（Opportunity Reminder 的基础）
  - 三层窗口：recent(最近) / last_week(一周) / all_time(全部)
  - confidence 自动计算
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import Counter

from ..event_types import Event, EventType
from .base import Projection


# ---- 数据结构 ----

@dataclass
class WindowStats:
    """一个时间窗口的统计"""
    message_count: int = 0
    user_count: int = 0
    assistant_count: int = 0
    days_span: int = 0
    messages_per_day: float = 0.0

    def to_dict(self) -> dict:
        return {
            "message_count": self.message_count,
            "user_count": self.user_count,
            "assistant_count": self.assistant_count,
            "days_span": self.days_span,
            "messages_per_day": round(self.messages_per_day, 1),
        }


@dataclass
class ConversationProfile:
    """对话分析结果"""
    person_name: str
    version: int = 1

    # 三层窗口
    recent: WindowStats | None = None      # 最近 20 条
    last_week: WindowStats | None = None   # 最近 7 天
    all_time: WindowStats | None = None    # 全部历史

    # 话题
    topic_frequency: dict[str, int] = field(default_factory=dict)
    top_topics: list[str] = field(default_factory=list)  # 最常见的 5 个话题

    # 密度
    conversation_density: str = ""     # "dense" / "normal" / "sparse"
    density_label: str = ""            # "很密集" / "正常" / "稀疏"

    # 时间
    first_chat: str = ""
    last_chat: str = ""

    # 置信度
    confidence: float = 0.0

    # 来源追溯
    derived_from: list[str] = field(default_factory=list)

    # metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "version": self.version,
            "recent": self.recent.to_dict() if self.recent else None,
            "last_week": self.last_week.to_dict() if self.last_week else None,
            "all_time": self.all_time.to_dict() if self.all_time else None,
            "topic_frequency": self.topic_frequency,
            "top_topics": self.top_topics,
            "conversation_density": self.conversation_density,
            "density_label": self.density_label,
            "first_chat": self.first_chat,
            "last_chat": self.last_chat,
            "confidence": round(self.confidence, 2),
            "derived_from": self.derived_from,
            "metadata": self.metadata,
        }


# ---- Projection ----

class ConversationProjection(Projection):
    """对话分析投影"""

    def project(self, events) -> dict[str, ConversationProfile]:
        profiles: dict[str, ConversationProfile] = {}
        event_list = list(events)

        by_person: dict[str, list[Event]] = {}
        for e in event_list:
            if e.type == EventType.CHAT and e.person:
                by_person.setdefault(e.person, []).append(e)

        for name, chat_events in by_person.items():
            profiles[name] = self._build_profile(name, chat_events, len(event_list))

        return profiles

    def project_one(self, events, name: str) -> ConversationProfile | None:
        return self.project(events).get(name)

    def _build_profile(self, name: str, events: list[Event], total_events: int) -> ConversationProfile:
        p = ConversationProfile(person_name=name)
        now = datetime.now(timezone.utc)

        # 按时间排序
        sorted_events = sorted(events, key=lambda e: e.occurred_at)
        timestamps = [self.parse_ts(e.occurred_at) for e in sorted_events]
        valid_ts = [ts for ts in timestamps if ts]

        # 来源追溯
        p.derived_from = [e.event_id for e in sorted_events]

        # 三层窗口
        p.recent = self._compute_window(sorted_events[-20:], valid_ts[-20:] if valid_ts else [])
        p.last_week = self._compute_window(
            [e for e in sorted_events if self._is_within_days(e.occurred_at, 7)],
            [ts for ts in valid_ts if (now - ts).days <= 7]
        )
        p.all_time = self._compute_window(sorted_events, valid_ts)

        # 话题频率
        topic_counter: Counter = Counter()
        for e in sorted_events:
            topics = e.data.get("topics", [])
            for t in topics:
                topic_counter[t] += 1
        p.topic_frequency = dict(topic_counter.most_common(20))
        p.top_topics = [t for t, _ in topic_counter.most_common(5)]

        # 密度
        if p.all_time and p.all_time.messages_per_day > 0:
            mpd = p.all_time.messages_per_day
            if mpd >= 5:
                p.conversation_density = "dense"
                p.density_label = "很密集"
            elif mpd >= 1:
                p.conversation_density = "normal"
                p.density_label = "正常"
            else:
                p.conversation_density = "sparse"
                p.density_label = "稀疏"

        # 时间
        if valid_ts:
            p.first_chat = valid_ts[0].isoformat()
            p.last_chat = valid_ts[-1].isoformat()

        # 置信度
        p.confidence = self._compute_confidence(sorted_events, valid_ts)

        # metadata
        p.metadata = {
            "generated_at": now.isoformat(),
            "source_event_count": total_events,
            "version": "1.0",
        }

        return p

    def _compute_window(self, events: list[Event], timestamps: list[datetime]) -> WindowStats:
        """计算一个时间窗口的统计"""
        if not events:
            return WindowStats()

        user_count = sum(1 for e in events if e.data.get("role") == "user")
        asst_count = sum(1 for e in events if e.data.get("role") == "assistant")

        days_span = 1
        if len(timestamps) >= 2:
            days_span = max(1, (timestamps[-1] - timestamps[0]).days)

        return WindowStats(
            message_count=len(events),
            user_count=user_count,
            assistant_count=asst_count,
            days_span=days_span,
            messages_per_day=len(events) / days_span,
        )

    def _compute_confidence(self, events: list[Event], timestamps: list[datetime]) -> float:
        """置信度：基于事件数量和时间跨度"""
        if not events:
            return 0.0
        count_score = min(1.0, len(events) / 50)  # 50条消息 → 满分
        if len(timestamps) >= 2:
            days = (timestamps[-1] - timestamps[0]).days
            time_score = min(1.0, days / 90)  # 90天 → 满分
        else:
            time_score = 0.1
        return (count_score * 0.6 + time_score * 0.4)

    def _is_within_days(self, ts_str: str, days: int) -> bool:
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - ts).days <= days
        except (ValueError, TypeError):
            return False


