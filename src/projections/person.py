"""Person Projection — 人物画像投影

从 person + fact 事件重建每个人物的完整画像。
输入：Event Log 中所有 person 和 fact 类型事件
输出：dict[str, PersonProfile]（人名 → 画像）

重建规则：
  - person 事件：增量更新人物属性（后面覆盖前面）
  - fact 事件：追加到 facts 列表
  - 第一个 person 事件决定 first_met 时间
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..event_types import Event, EventType
from .base import Projection


@dataclass
class FactRecord:
    """一条事实记录"""
    content: str
    category: str
    importance: int
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "importance": self.importance,
            "timestamp": self.timestamp,
        }


@dataclass
class PersonProfile:
    """人物画像"""
    name: str
    nickname: str = ""
    birthday: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    first_met: str = ""
    facts: list[FactRecord] = field(default_factory=list)
    fact_count: int = 0
    last_updated: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "nickname": self.nickname,
            "birthday": self.birthday,
            "tags": self.tags,
            "notes": self.notes,
            "first_met": self.first_met,
            "facts": [f.to_dict() for f in self.facts],
            "fact_count": self.fact_count,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }


class PersonProjection(Projection):
    """人物画像投影

    从 person + fact 事件流重建所有人物画像。
    """

    def project(self, events) -> dict[str, PersonProfile]:
        """输入事件流，输出 {人名: PersonProfile}"""
        profiles: dict[str, PersonProfile] = {}
        event_list = list(events)

        for e in event_list:
            if e.type == EventType.PERSON:
                self._apply_person_event(profiles, e)
            elif e.type == EventType.FACT:
                self._apply_fact_event(profiles, e)

        for p in profiles.values():
            p.metadata = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_event_count": len(event_list),
                "version": "1.0",
            }

        return profiles

    def project_one(self, events, name: str) -> PersonProfile | None:
        """只查询一个人的画像"""
        profiles = self.project(events)
        return profiles.get(name)

    def _apply_person_event(self, profiles: dict[str, PersonProfile], e: Event):
        """处理 person 事件：创建或增量更新"""
        name = e.person
        if not name:
            return

        if name not in profiles:
            profiles[name] = PersonProfile(name=name, first_met=e.timestamp)

        p = profiles[name]
        data = e.data

        if "nickname" in data:
            p.nickname = data["nickname"]
        if "birthday" in data:
            p.birthday = data["birthday"]
        if "tags" in data:
            p.tags = data["tags"]
        if "notes" in data:
            p.notes = data["notes"]

        p.last_updated = e.timestamp

    def _apply_fact_event(self, profiles: dict[str, PersonProfile], e: Event):
        """处理 fact 事件：追加事实"""
        name = e.person
        if not name:
            return

        if name not in profiles:
            profiles[name] = PersonProfile(name=name, first_met=e.timestamp)

        p = profiles[name]
        fact = FactRecord(
            content=e.data.get("content", ""),
            category=e.data.get("category", "general"),
            importance=e.data.get("importance", 5),
            timestamp=e.timestamp,
        )
        p.facts.append(fact)
        p.fact_count = len(p.facts)
        p.last_updated = e.timestamp
