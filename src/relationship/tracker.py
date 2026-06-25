"""关系追踪 - 记录关系阶段、关键事件、情感温度"""

import json
import os
from datetime import datetime
from pydantic import BaseModel, Field


class Event(BaseModel):
    """关系中的关键事件"""
    content: str
    event_type: str = "general"  # general, date, gift, argument, milestone, sweet
    emotional_impact: int = 0  # -10 到 +10
    date: str = Field(default_factory=lambda: datetime.now().isoformat())


class Relationship(BaseModel):
    """一段关系的完整记录"""
    person_name: str
    stage: str = "认识"  # 认识/朋友/暧昧/热恋/稳定/冷淡/分手
    chemistry: int = 50  # 好感度 0-100
    last_contact: str = Field(default_factory=lambda: datetime.now().isoformat())
    contact_frequency: str = "偶尔"  # 每天/经常/偶尔/很少
    events: list[Event] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class RelationshipTracker:
    """关系追踪器"""

    STAGES = ["认识", "朋友", "暧昧", "热恋", "稳定", "冷淡", "分手"]

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.file = os.path.join(data_dir, "relationships.json")
        os.makedirs(data_dir, exist_ok=True)
        self._relationships: dict[str, Relationship] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            with open(self.file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for name, rdata in data.items():
                    self._relationships[name] = Relationship(**rdata)

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(
                {name: r.model_dump() for name, r in self._relationships.items()},
                f, ensure_ascii=False, indent=2
            )

    def add_relationship(self, person_name: str, **kwargs) -> Relationship:
        if person_name in self._relationships:
            return self._relationships[person_name]
        rel = Relationship(person_name=person_name, **kwargs)
        self._relationships[person_name] = rel
        self._save()
        return rel

    def get(self, person_name: str) -> Relationship | None:
        return self._relationships.get(person_name)

    def list_all(self) -> list[Relationship]:
        return sorted(
            self._relationships.values(),
            key=lambda r: r.chemistry, reverse=True
        )

    def update_chemistry(self, person_name: str, delta: int) -> Relationship | None:
        rel = self._relationships.get(person_name)
        if not rel:
            return None
        rel.chemistry = max(0, min(100, rel.chemistry + delta))
        rel.updated_at = datetime.now().isoformat()
        self._save()
        return rel

    def update_stage(self, person_name: str, new_stage: str) -> Relationship | None:
        rel = self._relationships.get(person_name)
        if not rel:
            return None
        old_stage = rel.stage
        rel.stage = new_stage
        rel.milestones.append(
            f"{datetime.now().strftime('%Y-%m-%d')}: {old_stage} → {new_stage}"
        )
        rel.updated_at = datetime.now().isoformat()
        self._save()
        return rel

    def add_event(self, person_name: str, content: str,
                  event_type: str = "general", emotional_impact: int = 0) -> Event | None:
        rel = self._relationships.get(person_name)
        if not rel:
            return None
        event = Event(
            content=content, event_type=event_type,
            emotional_impact=emotional_impact
        )
        rel.events.append(event)
        rel.last_contact = datetime.now().isoformat()
        rel.chemistry = max(0, min(100, rel.chemistry + emotional_impact))
        rel.updated_at = datetime.now().isoformat()
        self._save()
        return event

    def touch(self, person_name: str) -> None:
        """更新最近联系时间"""
        rel = self._relationships.get(person_name)
        if rel:
            rel.last_contact = datetime.now().isoformat()
            self._save()

    def get_reminders(self) -> list[dict]:
        """生成提醒：太久没联系的人、即将到来的生日等"""
        reminders = []
        now = datetime.now()
        for name, rel in self._relationships.items():
            last = datetime.fromisoformat(rel.last_contact)
            days = (now - last).days
            if days > 7 and rel.stage in ("暧昧", "热恋"):
                reminders.append({
                    "person": name,
                    "type": "lost_contact",
                    "message": f"你已经 {days} 天没联系 {name} 了，关系可能会降温！",
                    "urgency": "high"
                })
            elif days > 14 and rel.stage in ("朋友", "认识"):
                reminders.append({
                    "person": name,
                    "type": "lost_contact",
                    "message": f"{name} 已经 {days} 天没联系了，要不要打个招呼？",
                    "urgency": "medium"
                })
        return reminders

    def stats(self) -> dict:
        stages = {}
        for rel in self._relationships.values():
            stages[rel.stage] = stages.get(rel.stage, 0) + 1
        return {
            "total": len(self._relationships),
            "by_stage": stages,
            "avg_chemistry": (
                sum(r.chemistry for r in self._relationships.values()) /
                len(self._relationships) if self._relationships else 0
            ),
        }
