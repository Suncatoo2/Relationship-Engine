"""Protocol Layer — Phase 1

所有模块说同一种语言。
ContextObject 是 Memory Engine 输出给所有 LLM 的统一协议。
"""

from dataclasses import dataclass, field


# ============================================================
#  Context Object v1 — 4 must blocks + 2 optional
# ============================================================

@dataclass(frozen=True)
class IdentityBlock:
    """must: 这是谁"""
    name: str = ""
    nickname: str = ""
    tags: list[str] = field(default_factory=list)
    birthday: str = ""
    days_known: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "nickname": self.nickname,
            "tags": self.tags,
            "birthday": self.birthday,
            "days_known": self.days_known,
        }


@dataclass(frozen=True)
class FactItem:
    """一条事实"""
    content: str = ""
    category: str = "general"
    confidence: float = 0.9
    importance: int = 5
    source: str = "user_direct"
    status: str = "active"
    created_at: str = ""           # ISO timestamp — used by RetrievalRanker for recency scoring

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "importance": self.importance,
            "source": self.source,
            "status": self.status,
        }


@dataclass(frozen=True)
class MemoryBlock:
    """must: 关于这个人我知道什么"""
    active_facts: list = field(default_factory=list)        # list[FactItem]
    fact_count: int = 0
    memory_summary: str = ""                                 # LLM-ready narrative
    top_topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "active_facts": [f.to_dict() for f in self.active_facts],
            "fact_count": self.fact_count,
            "memory_summary": self.memory_summary,
            "top_topics": self.top_topics,
        }


@dataclass(frozen=True)
class RelationshipBlock:
    """must: 关系怎样"""
    stage: str = "陌生人"
    chemistry: int = 0
    decay_chemistry: int = 0
    trend: str = "稳定"
    last_contact_summary: str = ""                           # LLM-ready: "3天前聊过"
    milestones: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "chemistry": self.chemistry,
            "decay_chemistry": self.decay_chemistry,
            "trend": self.trend,
            "last_contact_summary": self.last_contact_summary,
            "milestones": self.milestones,
        }


@dataclass(frozen=True)
class TimeBlock:
    """must: 时间感知"""
    last_chat_label: str = ""                                # "今天" / "3天前"
    silence_label: str = ""                                  # "刚聊完" / "很久没联系"
    upcoming: list[str] = field(default_factory=list)        # ["生日还有5天"]
    days_known: int = 0

    def to_dict(self) -> dict:
        return {
            "last_chat_label": self.last_chat_label,
            "silence_label": self.silence_label,
            "upcoming": self.upcoming,
            "days_known": self.days_known,
        }


@dataclass(frozen=True)
class EmotionBlock:
    """optional: 情绪状态"""
    trend: str = ""
    dominant_emotion: str = ""
    alert: str = ""

    def to_dict(self) -> dict:
        return {
            "trend": self.trend,
            "dominant_emotion": self.dominant_emotion,
            "alert": self.alert,
        }


@dataclass(frozen=True)
class GoalItem:
    """一条目标/梦想/承诺"""
    title: str = ""
    category: str = ""           # "dream" / "goal" / "commitment"
    target_date: str = ""        # "2027-06" 或空
    status: str = "active"       # "active" / "completed" / "abandoned"
    last_mentioned: str = ""     # 最近一次提到的时间
    confidence: float = 0.9

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "category": self.category,
            "target_date": self.target_date,
            "status": self.status,
            "last_mentioned": self.last_mentioned,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class GoalsBlock:
    """optional: 长期目标与梦想"""
    active_goals: list = field(default_factory=list)       # list[GoalItem]
    completed_goals: list = field(default_factory=list)    # list[GoalItem]
    goal_count: int = 0

    def to_dict(self) -> dict:
        return {
            "active_goals": [g.to_dict() for g in self.active_goals],
            "completed_goals": [g.to_dict() for g in self.completed_goals],
            "goal_count": self.goal_count,
        }


@dataclass(frozen=True)
class SystemBlock:
    """must: 元数据"""
    version: int = 1
    generated_at: str = ""
    event_count: int = 0
    token_estimate: int = 0

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "event_count": self.event_count,
            "token_estimate": self.token_estimate,
        }


@dataclass(frozen=True)
class ContextObject:
    """Memory Engine 输出给所有 LLM 的统一协议

    4 must blocks: identity / memory / relationship / time / system
    3 optional:    emotion / growth / goals
    版本校验:      last_consumed_event_id（读写一致性安全网）

    ⚠️ 冻结警告：这是最后一次结构性变更。
    以后只允许增加字段，不修改整体结构。
    """
    identity: IdentityBlock = field(default_factory=IdentityBlock)
    memory: MemoryBlock = field(default_factory=MemoryBlock)
    relationship: RelationshipBlock = field(default_factory=RelationshipBlock)
    time: TimeBlock = field(default_factory=TimeBlock)
    system: SystemBlock = field(default_factory=SystemBlock)
    emotion: EmotionBlock | None = None
    growth: dict | None = None          # reserved, v0.5
    goals: GoalsBlock | None = None     # Goal Engine 输出
    suggestions: list[str] = field(default_factory=list)  # Engine Detect (ADR-007)
    last_consumed_event_id: str = ""    # 版本校验：当前已消费的最新 event_id

    def to_dict(self) -> dict:
        d = {
            "identity": self.identity.to_dict(),
            "memory": self.memory.to_dict(),
            "relationship": self.relationship.to_dict(),
            "time": self.time.to_dict(),
            "system": self.system.to_dict(),
            "last_consumed_event_id": self.last_consumed_event_id,
        }
        if self.emotion:
            d["emotion"] = self.emotion.to_dict()
        if self.growth:
            d["growth"] = self.growth
        if self.goals:
            d["goals"] = self.goals.to_dict()
        if self.suggestions:
            d["suggestions"] = self.suggestions
        return d

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
