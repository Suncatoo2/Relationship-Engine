"""Storage — Event Store 抽象接口

ADR-004: 业务逻辑永远不直接读写文件，只能通过 Storage 接口。
ADR-006: 只有 Pipeline 可以访问 Storage。

当前实现: JSONLStorage（append-only JSONL）
未来实现: SQLiteStorage / PostgresStorage / GraphStorage
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timezone

from .event_types import Event


# ============================================================
#  抽象接口 — 3 个方法
# ============================================================

class Storage(ABC):
    """Event Store 抽象接口

    极简设计: 只有 3 个方法。
    以后需要时再加 (查询 / 搜索 / compact)，不在 Phase 1 做。
    """

    @abstractmethod
    def append(self, event: Event) -> Event:
        """追加一条事件到 Event Store。

        Storage 负责:
          - 生成 event_id (UUID)
          - 设置 recorded_at (当前 UTC 时间)
          - 保证原子性写入

        Args:
            event: 业务代码创建的 Event (event_id 和 recorded_at 可为空)

        Returns:
            同一个 Event 对象，event_id 和 recorded_at 已填充
        """
        ...

    @abstractmethod
    def read_all(self) -> Iterator[Event]:
        """读取所有事件（按写入顺序，即 recorded_at 升序）

        Returns:
            事件迭代器
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """事件总数"""
        ...

    @abstractmethod
    def read_since(self, event_id: str) -> Iterator[Event]:
        """增量读取：从指定 event_id 之后开始读取

        用于 Snapshot + Incremental Replay 场景：
          1. 加载 Snapshot (State @ Event_ID_X)
          2. read_since("Event_ID_X") → 只 replay 新事件
          3. 合并 → 当前状态

        Args:
            event_id: 起始 event_id（不包含该 event 本身）

        Returns:
            该 event_id 之后的所有事件（按写入顺序）
        """
        ...


# ============================================================
#  当前实现: JSONLStorage
# ============================================================

class JSONLStorage(Storage):
    """append-only JSONL 实现

    当前选择 JSONL 的原因:
      - 人类可读（可以直接打开看）
      - append-only（不会因 crash 损坏）
      - git 友好（可以 diff）
      - 数据量 < 10 万时性能完全够用
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.log_file = os.path.join(data_dir, "events.jsonl")
        os.makedirs(data_dir, exist_ok=True)

    def append(self, event: Event) -> Event:
        """追加事件 — 生成 event_id 和 recorded_at"""
        # Storage 层负责生成 ID 和时间戳
        if not event.event_id:
            object.__setattr__(event, "event_id", str(uuid.uuid4()))
        if not event.recorded_at:
            object.__setattr__(event, "recorded_at", datetime.now(timezone.utc).isoformat())

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        return event

    def read_all(self) -> Iterator[Event]:
        """逐条迭代所有事件"""
        if not os.path.exists(self.log_file):
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield Event.from_dict(json.loads(line))

    def read_since(self, event_id: str) -> Iterator[Event]:
        """增量读取：从指定 event_id 之后开始

        策略：逐行扫描，找到目标后 yield 后续所有事件。
        对 append-only JSONL，写入顺序 = event_id 顺序（近似）。
        """
        if not os.path.exists(self.log_file):
            return
        found = False
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = Event.from_dict(json.loads(line))
                if found:
                    yield event
                elif event.event_id == event_id:
                    found = True
        # 如果 event_id 不在文件中，返回空（安全降级）

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
