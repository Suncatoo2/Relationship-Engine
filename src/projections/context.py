"""Context Composer — 组合所有 Projection 的输出

只能读取 Profile，不能读取 Event Log。
职责：组合 + 预算控制 + 生成 ContextSnapshot。

数据流：
  Event Log → Projection → Profile → Context Composer → ContextSnapshot
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..event_types import Event
from .base import Projection
from .person import PersonProjection, PersonProfile
from .relationship import RelationshipProjection, RelationshipProfile
from .time_context import TimeContextProjection, TimeContextProfile
from .emotion import EmotionProjection, EmotionProfile
from .growth import GrowthProjection, GrowthProfile
from .conversation import ConversationProjection, ConversationProfile
from .reminder import ReminderProjection, ReminderProfile


# ---- 优先级 ----

class ProfilePriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


PRIORITY_MAP = {
    "relationship": ProfilePriority.HIGH,
    "reminder": ProfilePriority.HIGH,
    "person": ProfilePriority.MEDIUM,
    "conversation": ProfilePriority.MEDIUM,
    "emotion": ProfilePriority.MEDIUM,
    "growth": ProfilePriority.LOW,
    "time": ProfilePriority.LOW,
}


# ---- ContextSnapshot ----

@dataclass
class ContextSnapshot:
    """所有 Projection 的组合输出"""
    version: int = 1
    person: PersonProfile | None = None
    relationship: RelationshipProfile | None = None
    time: TimeContextProfile | None = None
    emotion: EmotionProfile | None = None
    growth: GrowthProfile | None = None
    conversation: ConversationProfile | None = None
    reminder: ReminderProfile | None = None
    excluded: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "version": self.version,
            "excluded": self.excluded,
            "metadata": self.metadata,
        }
        if self.person:
            d["person"] = self.person.to_dict()
        if self.relationship:
            d["relationship"] = self.relationship.to_dict()
        if self.time:
            d["time"] = self.time.to_dict()
        if self.emotion:
            d["emotion"] = self.emotion.to_dict()
        if self.growth:
            d["growth"] = self.growth.to_dict()
        if self.conversation:
            d["conversation"] = self.conversation.to_dict()
        if self.reminder:
            d["reminder"] = self.reminder.to_dict()
        return d


# ---- Budget ----

DEFAULT_BUDGET_LIMIT = 6000  # 默认 token 预算


# ---- Context Composer ----

class ContextComposer:
    """Context Composer — 组合所有 Projection

    只读 Profile，不读 Event Log。
    """

    def __init__(self, budget_limit: int = DEFAULT_BUDGET_LIMIT):
        self.budget_limit = budget_limit
        self.person_proj = PersonProjection()
        self.relationship_proj = RelationshipProjection()
        self.time_proj = TimeContextProjection()
        self.emotion_proj = EmotionProjection()
        self.growth_proj = GrowthProjection()
        self.conversation_proj = ConversationProjection()
        self.reminder_proj = ReminderProjection()

    def compose(self, events: list[Event], person_name: str) -> ContextSnapshot:
        """组合所有 Projection 为 ContextSnapshot

        Args:
            events: 事件列表（由 Pipeline 或调用方传入，不含 EventLog）
            person_name: 要查询的人物名
        """
        event_list = list(events)

        now = datetime.now(timezone.utc)

        # 生成所有 Profile
        person_profile = self.person_proj.project_one(event_list, person_name)
        relationship_profile = self.relationship_proj.project_one(event_list, person_name)
        time_profile = self.time_proj.project_one(event_list, person_name)
        emotion_profile = self.emotion_proj.project_one(event_list, person_name)
        growth_profile = self.growth_proj.project_one(event_list, person_name)
        conversation_profile = self.conversation_proj.project_one(event_list, person_name)
        reminder_profile = self.reminder_proj.project(event_list)

        # 按优先级组装，控制预算
        profiles = [
            ("relationship", relationship_profile),
            ("reminder", reminder_profile),
            ("person", person_profile),
            ("conversation", conversation_profile),
            ("emotion", emotion_profile),
            ("growth", growth_profile),
            ("time", time_profile),
        ]

        snapshot = ContextSnapshot(version=1)
        token_used = 0
        excluded = []

        for name, profile in profiles:
            if profile is None:
                continue
            profile_tokens = self._estimate_tokens(profile)
            if token_used + profile_tokens <= self.budget_limit:
                setattr(snapshot, name, profile)
                token_used += profile_tokens
            else:
                excluded.append(name)

        snapshot.excluded = excluded

        # 收集 Projection 版本
        proj_versions = {}
        for name, profile in profiles:
            if profile and hasattr(profile, "version"):
                proj_versions[name] = profile.version

        snapshot.metadata = {
            "version": 1,
            "generated_at": now.isoformat(),
            "person_name": person_name,
            "token_used": token_used,
            "budget_limit": self.budget_limit,
            "projection_versions": proj_versions,
            "event_count": len(event_list),
            "last_event_time": event_list[-1].occurred_at if event_list else "",
        }

        return snapshot

    def _estimate_tokens(self, profile) -> int:
        """粗略估算 Profile 序列化后的 token 数"""
        text = str(profile.to_dict() if hasattr(profile, "to_dict") else profile)
        # 粗略：1 token ≈ 2 个中文字符 或 4 个英文字符
        return len(text) // 2
