"""Event Log — Relationship Event OS 的存储层

Everything is Event.
Event Log 是整个系统唯一的 Source of Truth。
所有数据以 append-only JSONL 格式存储在 events.jsonl 中。
Projection 从 Event Log 读取事件流，计算出各种视图。

两种读取模式：
  - iter_events()  — 逐条迭代，内存恒定（推荐用于大数据量）
  - read_all()     — 全量读取，返回列表（适合小数据量）
"""

import json
import os
from collections.abc import Generator
from datetime import datetime, timezone, timedelta
from .event_types import Event


class EventLog:
    """append-only 事件日志

    所有事件存储在 data/events.jsonl 中，每行一个 JSON 对象。
    只追加，不修改，不删除。
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.log_file = os.path.join(data_dir, "events.jsonl")
        os.makedirs(data_dir, exist_ok=True)

    def append(self, event: Event) -> None:
        """追加一个事件到日志"""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    # ---- 迭代器（推荐：边读边 Replay，内存恒定） ----

    def iter_events(self) -> Generator[Event, None, None]:
        """逐条迭代所有事件（内存恒定，适合大数据量）"""
        if not os.path.exists(self.log_file):
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield Event.from_dict(json.loads(line))

    def iter_by_type(self, type: str) -> Generator[Event, None, None]:
        """按类型逐条过滤"""
        for e in self.iter_events():
            if e.type == type:
                yield e

    def iter_by_person(self, person: str) -> Generator[Event, None, None]:
        """按人物逐条过滤"""
        for e in self.iter_events():
            if e.person == person:
                yield e

    # ---- 列表读取（小数据量，简单场景） ----

    def read_all(self) -> list[Event]:
        """读取所有事件（返回列表）"""
        return list(self.iter_events())

    def read_by_type(self, type: str) -> list[Event]:
        """按事件类型过滤（返回列表）"""
        return list(self.iter_by_type(type))

    def read_by_person(self, person: str) -> list[Event]:
        """按人物过滤（返回列表）"""
        return list(self.iter_by_person(person))

    def read_recent(self, days: int = 30) -> list[Event]:
        """读取最近 N 天的事件"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = []
        for e in self.iter_events():
            try:
                ts = datetime.fromisoformat(e.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    result.append(e)
            except (ValueError, TypeError):
                result.append(e)
        return result

    def search(self, keyword: str) -> list[Event]:
        """在所有事件中搜索关键词（大小写不敏感）"""
        keyword_lower = keyword.lower()
        results = []
        for e in self.iter_events():
            if self._search_dict(e.data, keyword_lower):
                results.append(e)
                continue
            if keyword_lower in e.person.lower():
                results.append(e)
        return results

    def count(self) -> int:
        """事件总数"""
        if not os.path.exists(self.log_file):
            return 0
        count = 0
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def clear(self) -> None:
        """清空事件日志（仅用于测试）"""
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    @staticmethod
    def _search_dict(d: dict, keyword: str) -> bool:
        """递归搜索 dict 中是否包含关键词"""
        for v in d.values():
            if isinstance(v, str) and keyword in v.lower():
                return True
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and keyword in item.lower():
                        return True
        return False
