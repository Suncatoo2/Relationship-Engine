"""Relationship Projection — 关系状态投影

从 relation + chat + milestone + person 事件重建关系状态。
含好感度衰减模型、关系时间线、阶段变化历史。

输入事件类型：
  - person:   读取 tags 判断关系类型（用于衰减参数）
  - relation: 阶段变化、好感度变化
  - chat:     更新最后联系时间
  - milestone: 关系里程碑

输出：dict[str, RelationshipProfile]
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..event_types import Event, EventType, RelationStage, MilestoneType, DECAY_PARAMS
from .base import Projection


# ---- 数据结构 ----

@dataclass
class ChemistryRecord:
    """一条好感度变化记录"""
    delta: int
    reason: str
    timestamp: str
    event_id: str

    def to_dict(self) -> dict:
        return {
            "delta": self.delta,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }


@dataclass
class MilestoneRecord:
    """一条里程碑记录"""
    milestone_type: str
    description: str
    significance: int
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "milestone_type": self.milestone_type,
            "description": self.description,
            "significance": self.significance,
            "timestamp": self.timestamp,
        }


@dataclass
class TimelineEntry:
    """时间线中的一个节点"""
    timestamp: str
    entry_type: str  # "stage_change" / "event" / "milestone"
    content: str
    reason: str = ""

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "type": self.entry_type,
            "content": self.content,
        }
        if self.reason:
            d["reason"] = self.reason
        return d


@dataclass
class RelationshipProfile:
    """关系状态"""
    person_name: str
    relationship_type: str = "普通朋友"
    stage: str = RelationStage.STRANGER.value
    previous_stage: str = ""
    stage_changed_at: str = ""
    base_chemistry: int = 0
    decay_chemistry: int = 0
    floor: int = 10
    decay_rate: float = 0.02
    last_contact: str = ""
    last_contact_days: int = -1
    trend: str = "稳定"
    health: int = 50  # v2 预留，v3 完整实现
    chemistry_history: list[ChemistryRecord] = field(default_factory=list)
    milestones: list[MilestoneRecord] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "relationship_type": self.relationship_type,
            "stage": self.stage,
            "previous_stage": self.previous_stage,
            "stage_changed_at": self.stage_changed_at,
            "base_chemistry": self.base_chemistry,
            "decay_chemistry": self.decay_chemistry,
            "floor": self.floor,
            "decay_rate": self.decay_rate,
            "last_contact": self.last_contact,
            "last_contact_days": self.last_contact_days,
            "trend": self.trend,
            "health": self.health,
            "chemistry_history": [c.to_dict() for c in self.chemistry_history],
            "milestones": [m.to_dict() for m in self.milestones],
            "timeline": [t.to_dict() for t in self.timeline],
            "metadata": self.metadata,
        }


# ---- Projection ----

class RelationshipProjection(Projection):
    """关系状态投影

    从 relation + chat + milestone + person 事件流重建所有关系状态。
    """

    def project(self, events) -> dict[str, RelationshipProfile]:
        """输入事件流，输出 {人名: RelationshipProfile}"""
        profiles: dict[str, RelationshipProfile] = {}
        event_list = list(events)  # 需要多次遍历

        # Pass 1: 从 person 事件读取关系类型标签
        for e in event_list:
            if e.type == EventType.PERSON and e.person:
                self._apply_person_event(profiles, e)

        # Pass 2: 处理 relation + chat + milestone 事件
        for e in event_list:
            if e.type == EventType.RELATION and e.person:
                self._apply_relation_event(profiles, e)
            elif e.type == EventType.CHAT and e.person:
                self._apply_chat_event(profiles, e)
            elif e.type == EventType.MILESTONE and e.person:
                self._apply_milestone_event(profiles, e)

        # Pass 3: 计算运行时值（衰减、趋势、时间线）
        for p in profiles.values():
            self._compute_runtime(p)

        # 添加 metadata
        for p in profiles.values():
            p.metadata = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_event_count": len(event_list),
                "version": "1.0",
            }

        return profiles

    def project_one(self, events, name: str) -> RelationshipProfile | None:
        """只查询一个人的关系状态"""
        profiles = self.project(events)
        return profiles.get(name)

    # ---- 事件处理 ----

    def _ensure_profile(self, profiles: dict, name: str) -> RelationshipProfile:
        if name not in profiles:
            profiles[name] = RelationshipProfile(person_name=name)
        return profiles[name]

    def _apply_person_event(self, profiles: dict, e: Event):
        """从 person 事件读取关系类型"""
        p = self._ensure_profile(profiles, e.person)
        tags = e.data.get("tags", [])
        if tags:
            p.relationship_type = tags[0]

    def _apply_relation_event(self, profiles: dict, e: Event):
        """处理 relation 事件：阶段变化 + 好感度变化"""
        p = self._ensure_profile(profiles, e.person)
        data = e.data

        # 阶段变化
        if "stage" in data and data["stage"]:
            new_stage = data["stage"]
            if new_stage != p.stage:
                p.previous_stage = p.stage
                p.stage = new_stage
                p.stage_changed_at = e.timestamp
                reason = data.get("event", "")
                p.timeline.append(TimelineEntry(
                    timestamp=e.timestamp,
                    entry_type="stage_change",
                    content=f"{p.previous_stage} → {new_stage}",
                    reason=reason,
                ))

        # 好感度变化
        delta = data.get("delta", 0)
        if delta != 0:
            p.base_chemistry += delta
            reason = data.get("event", "关系变化")
            record = ChemistryRecord(
                delta=delta,
                reason=reason,
                timestamp=e.timestamp,
                event_id=e.id,
            )
            p.chemistry_history.append(record)
            p.timeline.append(TimelineEntry(
                timestamp=e.timestamp,
                entry_type="event",
                content=reason,
            ))

        p.last_contact = e.timestamp

    def _apply_chat_event(self, profiles: dict, e: Event):
        """处理 chat 事件：更新最后联系时间"""
        p = self._ensure_profile(profiles, e.person)
        p.last_contact = e.timestamp

    def _apply_milestone_event(self, profiles: dict, e: Event):
        """处理 milestone 事件：记录里程碑"""
        p = self._ensure_profile(profiles, e.person)
        data = e.data
        record = MilestoneRecord(
            milestone_type=data.get("milestone_type", "custom"),
            description=data.get("description", ""),
            significance=data.get("significance", 5),
            timestamp=e.timestamp,
        )
        p.milestones.append(record)
        p.timeline.append(TimelineEntry(
            timestamp=e.timestamp,
            entry_type="milestone",
            content=record.description,
        ))

    # ---- 运行时计算 ----

    def _compute_runtime(self, p: RelationshipProfile):
        """计算运行时值：衰减、趋势、时间差"""
        # 衰减参数
        params = DECAY_PARAMS.get(p.relationship_type, {"lambda": 0.02, "floor": 10})
        p.decay_rate = params["lambda"]
        p.floor = params["floor"]

        # 时间差
        if p.last_contact:
            p.last_contact_days = self.days_since(p.last_contact)
        else:
            p.last_contact_days = -1

        # 衰减计算
        if p.last_contact_days >= 0:
            factor = 1.0 / (1.0 + p.decay_rate * p.last_contact_days)
            p.decay_chemistry = max(p.floor, int(p.base_chemistry * factor + p.floor))
        else:
            p.decay_chemistry = p.base_chemistry

        # 趋势（最近 30 天的 chemistry 变化）
        p.trend = self._compute_trend(p.chemistry_history, days=30)

        # 排序 timeline
        p.timeline.sort(key=lambda t: t.timestamp)

    def _compute_trend(self, history: list[ChemistryRecord], days: int = 30) -> str:
        """根据最近 N 天的 chemistry 变化计算趋势"""
        if not history:
            return "稳定"

        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)
        recent_delta = 0
        for r in history:
            try:
                ts = datetime.fromisoformat(r.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    recent_delta += r.delta
            except (ValueError, TypeError):
                pass

        if recent_delta >= 15:
            return "升温"
        elif recent_delta <= -15:
            return "降温"
        else:
            return "稳定"
