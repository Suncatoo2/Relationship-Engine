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
    2 optional:    emotion / growth
    """
    identity: IdentityBlock = field(default_factory=IdentityBlock)
    memory: MemoryBlock = field(default_factory=MemoryBlock)
    relationship: RelationshipBlock = field(default_factory=RelationshipBlock)
    time: TimeBlock = field(default_factory=TimeBlock)
    system: SystemBlock = field(default_factory=SystemBlock)
    emotion: EmotionBlock | None = None
    growth: dict | None = None          # reserved, v0.5

    def to_dict(self) -> dict:
        d = {
            "identity": self.identity.to_dict(),
            "memory": self.memory.to_dict(),
            "relationship": self.relationship.to_dict(),
            "time": self.time.to_dict(),
            "system": self.system.to_dict(),
        }
        if self.emotion:
            d["emotion"] = self.emotion.to_dict()
        if self.growth:
            d["growth"] = self.growth
        return d

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
