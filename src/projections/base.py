"""Projection Base — 所有 Projection 的基类

Projection = f(events) → view

每个 Projection 从 Event Log 读取事件流，计算出一个结构化视图。
Projection 不存储任何数据，每次被调用时从事件流重新计算。
Event Log 变了，Projection 的输出自然变。
"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from datetime import datetime, timezone, timedelta

from ..event_types import Event


class Projection(ABC):
    """所有 Projection 的抽象基类

    子类只需实现 project() 方法：
        def project(self, events) -> dict
    """

    @abstractmethod
    def project(self, events: list[Event] | Generator) -> dict:
        """输入事件流，输出结构化视图

        Args:
            events: 事件列表或迭代器

        Returns:
            结构化 dict，具体内容由子类定义
        """
        ...

    # ---- 通用辅助方法 ----

    @staticmethod
    def filter_by_type(events, type: str) -> list[Event]:
        """按事件类型过滤"""
        return [e for e in events if e.type == type]

    @staticmethod
    def filter_by_person(events, person: str) -> list[Event]:
        """按人物过滤"""
        return [e for e in events if e.person == person]

    @staticmethod
    def filter_by_days(events, days: int) -> list[Event]:
        """过滤出最近 N 天的事件"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = []
        for e in events:
            try:
                ts = datetime.fromisoformat(e.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    result.append(e)
            except (ValueError, TypeError):
                result.append(e)
        return result

    @staticmethod
    def sort_by_time(events: list[Event], desc: bool = True) -> list[Event]:
        """按时间排序"""
        def _ts(e):
            try:
                return datetime.fromisoformat(e.timestamp)
            except (ValueError, TypeError):
                return datetime.min.replace(tzinfo=timezone.utc)
        return sorted(events, key=_ts, reverse=desc)

    @staticmethod
    def days_since(timestamp_str: str) -> int:
        """计算某个时间戳距今多少天"""
        try:
            ts = datetime.fromisoformat(timestamp_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - ts
            return max(0, delta.days)
        except (ValueError, TypeError):
            return -1

    @staticmethod
    def get_latest(events: list[Event]) -> Event | None:
        """获取最新的事件"""
        if not events:
            return None
        def _ts(e):
            try:
                return datetime.fromisoformat(e.timestamp)
            except (ValueError, TypeError):
                return datetime.min.replace(tzinfo=timezone.utc)
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
