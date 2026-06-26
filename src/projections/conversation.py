"""Conversation Projection — 对话历史投影

从 chat 事件重建对话历史。
这是最简单的 Projection——直接 replay，不做复杂计算。

输入事件类型：
  - chat: role, content, timestamp

输出：dict[str, ConversationProfile]
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..event_types import Event, EventType
from .base import Projection


@dataclass
class ChatMessage:
    """一条聊天消息"""
    role: str
    content: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class ConversationProfile:
    """对话历史"""
    person_name: str
    version: int = 1
    recent_messages: list[ChatMessage] = field(default_factory=list)
    total_messages: int = 0
    first_chat: str = ""
    last_chat: str = ""
    avg_messages_per_day: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "version": self.version,
            "recent_messages": [m.to_dict() for m in self.recent_messages],
            "total_messages": self.total_messages,
            "first_chat": self.first_chat,
            "last_chat": self.last_chat,
            "avg_messages_per_day": round(self.avg_messages_per_day, 1),
            "metadata": self.metadata,
        }


class ConversationProjection(Projection):
    """对话历史投影"""

    def __init__(self, recent_limit: int = 50):
        self.recent_limit = recent_limit

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

        # 按时间排序
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        # 消息列表
        messages = [
            ChatMessage(
                role=e.data.get("role", "user"),
                content=e.data.get("content", ""),
                timestamp=e.timestamp,
            )
            for e in sorted_events
        ]

        p.total_messages = len(messages)
        p.recent_messages = messages[-self.recent_limit:]

        # 时间统计
        if messages:
            p.first_chat = messages[0].timestamp
            p.last_chat = messages[-1].timestamp
            p.avg_messages_per_day = self._calc_avg_per_day(messages)

        p.metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_event_count": total_events,
            "version": "1.0",
        }

        return p

    def _calc_avg_per_day(self, messages: list[ChatMessage]) -> float:
        """计算日均消息数"""
        if len(messages) < 2:
            return float(len(messages))
        try:
            first = datetime.fromisoformat(messages[0].timestamp)
            last = datetime.fromisoformat(messages[-1].timestamp)
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = max(1, (last - first).days)
            return len(messages) / days
        except (ValueError, TypeError):
            return 0.0
