"""Event Types — Relationship Event OS 的数据基石

Everything is Event.
这是整个系统唯一的 Event 数据结构定义。
所有数据都以 Event 形式存储在 Event Log 中。
"""

import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    """事件类型枚举"""
    PERSON = "person"
    CHAT = "chat"
    FACT = "fact"
    EMOTION = "emotion"
    RELATION = "relation"
    MILESTONE = "milestone"
    GROWTH = "growth"
    REMINDER = "reminder"


class RelationStage(str, Enum):
    """关系阶段枚举（状态图，不是线性）"""
    STRANGER = "陌生人"
    ACQUAINTANCE = "认识"
    CHATTING = "聊天"
    FAMILIAR = "熟悉"
    FRIEND = "朋友"
    IMPORTANT = "重要的人"
    LONG_TERM = "长期陪伴"
    AMBIGUOUS = "暧昧"
    PASSIONATE = "热恋"
    STABLE = "稳定"
    COLD = "冷淡"
    BROKEN_UP = "分手"


class MilestoneType(str, Enum):
    """里程碑类型枚举"""
    FIRST_MEET = "first_meet"
    FIRST_CHAT = "first_chat"
    FIRST_DEEP_TALK = "first_deep_talk"
    FIRST_SECRET = "first_secret"
    FIRST_FIGHT = "first_fight"
    FIRST_RECONCILIATION = "first_reconciliation"
    FIRST_DATE = "first_date"
    FIRST_TRIP = "first_trip"
    FIRST_COLLABORATION = "first_collaboration"
    CUSTOM = "custom"


class GrowthCategory(str, Enum):
    """成长类型枚举"""
    SKILL = "skill"
    EXPERIENCE = "experience"
    MILESTONE = "milestone"
    ACHIEVEMENT = "achievement"
    REALIZATION = "realization"


class FactCategory(str, Enum):
    """事实分类枚举"""
    GENERAL = "general"
    PREFERENCE = "preference"
    BIRTHDAY = "birthday"
    HOBBY = "hobby"
    STORY = "story"
    IMPORTANT = "important"
    SECRET = "secret"


class EmotionLabel(str, Enum):
    """情绪标签建议（非强制，调用方 AI 可自定义）"""
    HAPPY = "开心"
    SAD = "难过"
    ANXIOUS = "焦虑"
    CALM = "平静"
    EXCITED = "兴奋"
    ANGRY = "愤怒"
    STRESSED = "压力"
    BORED = "无聊"
    NERVOUS = "紧张"
    TIRED = "疲惫"


# 关系衰减参数
DECAY_PARAMS = {
    "家人":   {"lambda": 0.001, "floor": 60},
    "挚友":   {"lambda": 0.005, "floor": 30},
    "普通朋友": {"lambda": 0.02,  "floor": 10},
    "暧昧":   {"lambda": 0.05,  "floor": 5},
    "同事":   {"lambda": 0.03,  "floor": 5},
}


@dataclass
class Event:
    """Event — 系统中唯一的数据结构

    所有数据都以 Event 形式存储。
    Memory、Relationship、Time、Emotion、Growth、Reminder 全是 Event 的 Projection。

    Fields:
        event_id:    全局唯一 ID，由 Storage/Pipeline 在 append 时生成
        occurred_at: 业务发生时间（用户说话的真实时刻）
        recorded_at: 系统写入时间（Storage append 的时刻）
        version:     Schema 版本号（当前为 1，未来演进时递增）
        type:        事件类型
        data:        事件载荷
        person:      涉及人物
        source:      来源标识
    """
    event_id: str
    occurred_at: str
    type: str
    data: dict
    person: str = ""
    source: str = "user_input"
    version: int = 1
    recorded_at: str = ""

    def to_dict(self) -> dict:
        """序列化为 dict（用于写入 JSONL）"""
        d = {
            "event_id": self.event_id,
            "occurred_at": self.occurred_at,
            "type": self.type,
            "data": self.data,
            "version": self.version,
            "recorded_at": self.recorded_at,
        }
        if self.person:
            d["person"] = self.person
        if self.source:
            d["source"] = self.source
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        """从 dict 反序列化（用于从 JSONL 读取）

        兼容旧格式：
          - 旧 key "id"        → event_id
          - 旧 key "timestamp" → occurred_at
          - 缺少 version       → 1
          - 缺少 recorded_at   → occurred_at 的值
        """
        return cls(
            event_id=d.get("event_id", d.get("id", "")),
            occurred_at=d.get("occurred_at", d.get("timestamp", "")),
            type=d["type"],
            data=d["data"],
            person=d.get("person", ""),
            source=d.get("source", "user_input"),
            version=d.get("version", 1),
            recorded_at=d.get("recorded_at", d.get("occurred_at", d.get("timestamp", ""))),
        )


def create_event(
    type: str,
    data: dict,
    person: str = "",
    source: str = "user_input",
    occurred_at: str | None = None,
    version: int = 1,
) -> Event:
    """创建 Event 的工厂函数

    event_id 和 recorded_at 由 Storage/Pipeline 在 append 时生成。
    业务代码只提供 occurred_at 和 version。

    Args:
        type:        事件类型
        data:        事件载荷
        person:      涉及人物
        source:      来源标识
        occurred_at: 业务发生时间（None 则使用当前 UTC 时间）
        version:     Schema 版本号
    """
    from datetime import datetime, timezone
    return Event(
        event_id="",                                          # Storage 生成
        occurred_at=occurred_at or datetime.now(timezone.utc).isoformat(),
        type=type,
        data=data,
        person=person,
        source=source,
        version=version,
        recorded_at="",                                        # Storage 生成
    )
