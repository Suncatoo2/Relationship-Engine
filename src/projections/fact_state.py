"""Fact Projection — 事实状态投影

从 Event Log 投影出每个人的事实状态。
Stateless + Immutable — 纯函数设计。

每个 category 有且仅有一个 active fact。
新 fact 自动 deprecate 同 category 的旧 fact。

输入：list[Event]
输出：FactState（frozen dataclass）
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .base import Projection


@dataclass(frozen=True)
class FactItem:
    """一条不可变的事实记录"""
    content: str = ""
    category: str = "general"
    importance: int = 5
    importance_reason: str = ""
    source: str = "user_direct"
    confidence: float = 0.9
    status: str = "active"
    memory_id: str = ""
    times_confirmed: int = 1
    created_at: str = ""
    last_confirmed: str = ""
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "importance": self.importance,
            "importance_reason": self.importance_reason,
            "source": self.source,
            "confidence": self.confidence,
            "status": self.status,
            "memory_id": self.memory_id,
            "times_confirmed": self.times_confirmed,
            "created_at": self.created_at,
            "last_confirmed": self.last_confirmed,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class FactState:
    """不可变的事实状态

    - active: category → 唯一的 active fact
    - deprecated: 被废弃的 fact 列表
    - all: 全部事实（按时间排序）
    """
    person_name: str = ""
    active: dict = field(default_factory=dict)       # {category: FactItem}
    deprecated: list = field(default_factory=list)    # [FactItem]
    all: list = field(default_factory=list)           # [FactItem]
    total: int = 0
    active_count: int = 0

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "active": {cat: f.to_dict() for cat, f in self.active.items()},
            "deprecated": [f.to_dict() for f in self.deprecated],
            "all": [f.to_dict() for f in self.all],
            "total": self.total,
            "active_count": self.active_count,
        }

    def get_active_content(self, category: str) -> str:
        """获取某个 category 的 active 事实内容"""
        f = self.active.get(category)
        return f.content if f else ""


class FactProjection(Projection):
    """事实状态投影

    两种使用模式：
      1. 批量（纯函数）：project(events) → FactState
      2. 增量（Pipeline）：apply(event) 维护内部缓存，project() 从缓存返回

    每个 category 有且仅有一个 active fact。
    """

    def __init__(self):
        self._cache: list = []  # apply() 累积的 fact events

    def apply(self, event):
        """增量模式：接收单个 fact event，追加到内部缓存

        由 Pipeline 通过 Dispatcher 调用。
        只处理 type=="fact" 的事件。
        """
        if event.type == "fact":
            self._cache.append(event)

    def snapshot(self) -> dict:
        """返回当前缓存状态的序列化快照"""
        state = self.project(self._cache)
        return state.to_dict()

    def project(self, events, person: str = "", since: str = None) -> FactState:
        """输入事件流，输出事实状态

        Args:
            events: Event 列表
            person: 按人物过滤（空字符串 = 不过滤）
            since: 预留增量接口（当前未实现）

        Returns:
            FactState（frozen dataclass）
        """
        # 过滤 fact 事件
        fact_events = [e for e in events if e.type == "fact"]
        if person:
            fact_events = [e for e in fact_events if e.person == person]

        # 按时间排序
        fact_events.sort(key=lambda e: e.occurred_at)

        # 构建 state：按 category 分组，最新 active 覆盖旧值
        all_facts: list[FactItem] = []
        deprecated_facts: list[FactItem] = []
        active_by_cat: dict[str, FactItem] = {}

        for e in fact_events:
            d = e.data
            item = FactItem(
                content=d.get("content", ""),
                category=d.get("category", "general"),
                importance=d.get("importance", 5),
                importance_reason=d.get("importance_reason", ""),
                source=d.get("source", "user_direct"),
                confidence=d.get("confidence", 0.9),
                status=d.get("status", "active"),
                memory_id=d.get("memory_id", ""),
                times_confirmed=d.get("times_confirmed", 1),
                created_at=e.occurred_at,
                last_confirmed=d.get("last_confirmed", ""),
                provenance=d.get("provenance", {}),
            )
            all_facts.append(item)

            # 同 category 只有最新 active 生效
            cat = item.category
            prev = active_by_cat.get(cat)
            if prev and prev.status in ("active", "confirmed"):
                # 旧值被新值覆盖 → deprecated
                deprecated_facts.append(prev)

            if item.status in ("active", "confirmed", "validated"):
                active_by_cat[cat] = item

        return FactState(
            person_name=person,
            active=active_by_cat,
            deprecated=deprecated_facts,
            all=all_facts,
            total=len(all_facts),
            active_count=len(active_by_cat),
        )

    def project_one(self, events, name: str) -> FactState:
        return self.project(events, person=name)
