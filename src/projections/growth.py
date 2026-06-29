"""Growth Projection — 成长时间线投影

记录一个人的成长变化，不是简历。
成长 = 能力、认知、习惯、价值观的变化。

输入事件类型：
  - growth: title, category, description, impact_level, date

输出：dict[str, GrowthProfile]

设计原则：
  Projection 只忠实 replay growth 事件，不推断成长。
  成长事件的质量取决于调用方 AI 写入的内容。
  MCP Tool 的 add_growth 应该引导 AI 记录"变化"而非"完成"。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import Counter

from ..event_types import Event, EventType
from .base import Projection


# ---- 数据结构 ----

@dataclass
class GrowthNode:
    """一个成长节点"""
    title: str
    category: str           # skill / experience / milestone / achievement / realization
    description: str
    impact_level: int       # 1-10
    date: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "impact_level": self.impact_level,
            "date": self.date,
            "timestamp": self.timestamp,
        }


@dataclass
class GrowthMilestone:
    """成长里程碑"""
    title: str
    description: str
    impact_level: int
    date: str
    category: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "impact_level": self.impact_level,
            "date": self.date,
            "category": self.category,
        }


@dataclass
class GrowthTrajectory:
    """成长轨迹（结构化数据，不生成自然语言）"""
    dominant_category: str      # 最常见的成长类型
    direction: str              # technical / creative / social / personal / academic
    high_impact_count: int      # 高影响力节点数量
    recent_categories: list[str]  # 最近 3 个节点的类型

    def to_dict(self) -> dict:
        return {
            "dominant_category": self.dominant_category,
            "direction": self.direction,
            "high_impact_count": self.high_impact_count,
            "recent_categories": self.recent_categories,
        }


@dataclass
class GrowthProfile:
    """成长状态"""
    person_name: str
    timeline: list[GrowthNode] = field(default_factory=list)
    milestones: list[GrowthMilestone] = field(default_factory=list)
    total_nodes: int = 0
    trajectory: GrowthTrajectory | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "timeline": [n.to_dict() for n in self.timeline],
            "milestones": [m.to_dict() for m in self.milestones],
            "total_nodes": self.total_nodes,
            "trajectory": self.trajectory.to_dict() if self.trajectory else None,
            "metadata": self.metadata,
        }


# ---- 方向映射 ----

CATEGORY_TO_DIRECTION = {
    "skill": "technical",
    "experience": "personal",
    "milestone": "personal",
    "achievement": "technical",
    "realization": "personal",
}


# ---- Projection ----

class GrowthProjection(Projection):
    """成长时间线投影"""

    def __init__(self):
        self._cache: list = []

    def apply(self, event: Event):
        """增量模式：缓存单个 growth event"""
        if event.type == EventType.GROWTH and event.person:
            self._cache.append(event)

    def snapshot(self) -> dict:
        """返回当前缓存状态的序列化快照"""
        return {
            name: p.to_dict()
            for name, p in self.project(self._cache).items()
        }

    def project(self, events) -> dict[str, GrowthProfile]:
        profiles: dict[str, GrowthProfile] = {}
        event_list = list(events)
        by_person: dict[str, list[Event]] = {}
        for e in event_list:
            if e.type == EventType.GROWTH and e.person:
                by_person.setdefault(e.person, []).append(e)
        for name, growth_events in by_person.items():
            profiles[name] = self._build_profile(name, growth_events, len(event_list))
        return profiles

    def project_one(self, events, name: str) -> GrowthProfile | None:
        return self.project(events).get(name)

    def _build_profile(self, name: str, events: list[Event], total_events: int) -> GrowthProfile:
        p = GrowthProfile(person_name=name)

        # 解析所有 growth 事件
        nodes = []
        for e in events:
            data = e.data
            nodes.append(GrowthNode(
                title=data.get("title", ""),
                category=data.get("category", "experience"),
                description=data.get("description", ""),
                impact_level=data.get("impact_level", 5),
                date=data.get("date", e.occurred_at[:10]),
                timestamp=e.occurred_at,
            ))

        # 按 date 排序
        nodes.sort(key=lambda n: n.date)
        p.timeline = nodes
        p.total_nodes = len(nodes)

        # 提取里程碑（impact_level >= 8）
        p.milestones = [
            GrowthMilestone(
                title=n.title,
                description=n.description,
                impact_level=n.impact_level,
                date=n.date,
                category=n.category,
            )
            for n in nodes if n.impact_level >= 8
        ]

        # 轨迹
        if nodes:
            p.trajectory = self._compute_trajectory(nodes)

        # metadata
        p.metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_event_count": total_events,
            "version": "1.0",
        }

        return p

    def _compute_trajectory(self, nodes: list[GrowthNode]) -> GrowthTrajectory:
        """计算成长轨迹（结构化数据）"""
        # 最常见类型
        categories = [n.category for n in nodes]
        dominant = Counter(categories).most_common(1)[0][0] if categories else "experience"

        # 最近 3 个节点类型
        recent = [n.category for n in nodes[-3:]]

        # 方向
        direction_votes = [CATEGORY_TO_DIRECTION.get(c, "personal") for c in categories]
        direction = Counter(direction_votes).most_common(1)[0][0] if direction_votes else "personal"

        # 高影响力节点
        high_impact = sum(1 for n in nodes if n.impact_level >= 8)

        return GrowthTrajectory(
            dominant_category=dominant,
            direction=direction,
            high_impact_count=high_impact,
            recent_categories=recent,
        )
