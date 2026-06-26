"""Projection Base — 所有 Projection 的基类

Projection = f(events) → view

每个 Projection 从 Event Log 读取事件流，计算出一个结构化视图。
Projection 不存储任何数据，每次被调用时从事件流重新计算。
Event Log 变了，Projection 的输出自然变。
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

from ..event_types import Event


class Projection(ABC):
    """所有 Projection 的抽象基类

    子类只需实现 project() 方法：
        def project(self, events) -> dict
    """

    @abstractmethod
    def project(self, events: list[Event]) -> dict:
        """输入事件流，输出结构化视图"""
        ...

    def project_one(self, events: list[Event], name: str):
        """查询单个人的 Profile（默认实现）"""
        profiles = self.project(events)
        return profiles.get(name)

    # ---- 通用辅助方法 ----

    @staticmethod
    def parse_ts(timestamp_str: str) -> datetime | None:
        """解析时间戳字符串，统一处理时区"""
        try:
            ts = datetime.fromisoformat(timestamp_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        except (ValueError, TypeError):
            return None

    @staticmethod
    def filter_by_event_type(events: list[Event], event_type: str) -> list[Event]:
        """按事件类型过滤"""
        return [e for e in events if e.type == event_type]

    # 兼容旧名
    filter_by_type = filter_by_event_type

    @staticmethod
    def filter_by_person(events: list[Event], person: str) -> list[Event]:
        """按人物过滤"""
        return [e for e in events if e.person == person]

    @staticmethod
    def filter_by_days(events: list[Event], days: int) -> list[Event]:
        """过滤出最近 N 天的事件"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = []
        for e in events:
            ts = Projection.parse_ts(e.timestamp)
            if ts is None:
                result.append(e)
            elif ts >= cutoff:
                result.append(e)
        return result

    @staticmethod
    def sort_by_time(events: list[Event], desc: bool = True) -> list[Event]:
        """按时间排序"""
        def _ts(e):
            return Projection.parse_ts(e.timestamp) or datetime.min.replace(tzinfo=timezone.utc)
        return sorted(events, key=_ts, reverse=desc)

    @staticmethod
    def days_since(timestamp_str: str) -> int:
        """计算某个时间戳距今多少天"""
        ts = Projection.parse_ts(timestamp_str)
        if ts is None:
            return -1
        delta = datetime.now(timezone.utc) - ts
        return max(0, delta.days)

    @staticmethod
    def get_latest(events: list[Event]) -> Event | None:
        """获取最新的事件"""
        if not events:
            return None
        def _ts(e):
            return Projection.parse_ts(e.timestamp) or datetime.min.replace(tzinfo=timezone.utc)
        return max(events, key=_ts)

    @staticmethod
    def unique_persons(events: list[Event]) -> list[str]:
        """获取所有不重复的人名"""
        seen = set()
        result = []
        for e in events:
            if e.person and e.person not in seen:
                seen.add(e.person)
                result.append(e.person)
        return result

    @staticmethod
    def count_by_type(events: list[Event]) -> dict[str, int]:
        """按类型统计事件数量"""
        counts: dict[str, int] = {}
        for e in events:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts

    @staticmethod
    def group_by_person(events: list[Event]) -> dict[str, list[Event]]:
        """按人物分组事件"""
        by_person: dict[str, list[Event]] = {}
        for e in events:
            if e.person:
                by_person.setdefault(e.person, []).append(e)
        return by_person

    @staticmethod
    def make_metadata(event_count: int, version: str = "1.0") -> dict:
        """生成统一的 metadata 字典"""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_event_count": event_count,
            "version": version,
        }
