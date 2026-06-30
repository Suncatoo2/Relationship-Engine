"""Storage — Event Store 抽象接口

ADR-004: 业务逻辑永远不直接读写文件，只能通过 Storage 接口。
ADR-006: 只有 Pipeline 可以访问 Storage。

当前实现: JSONLStorage（append-only JSONL）
未来实现: SQLiteStorage / PostgresStorage / GraphStorage

Interface contract (ADR-004 + ADR-006):
  Storage ABC defines 4 abstract methods + health() as optional.
  All adapters MUST implement: append, read_all, read_since, count.
  All adapters SHOULD implement: health().

  Pipeline depends on Storage ABC, never on JSONLStorage directly.
  This is dependency inversion — the seam was defined at v0.4.
"""

import json
import os
import uuid
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timezone
from dataclasses import dataclass

from .event_types import Event


# ============================================================
#  Capability Guard — 轻量 runtime enforcement
# ============================================================

@dataclass(frozen=True)
class StorageCapability:
    """Storage 访问令牌 — 只有 Pipeline 可以创建

    非 Pipeline 调用 Storage.append() → ArchitectureViolation (Fail Fast)

    设计理由:
      - O(1) 检查，零 AST 扫描开销
      - Pipeline 在 __init__ 时创建 token 注入 Storage
      - 测试可通过 StorageCapability("test") 创建合法 token
      - 这是架构约束的 runtime enforcement，不是安全机制
    """
    _token: str


# ============================================================
#  ArchitectureViolation — Fail Fast
# ============================================================

class ArchitectureViolation(RuntimeError):
    """架构违规 — 代码绕过了 Pipeline 直接访问 Storage"""
    pass


# ============================================================
#  抽象接口 — 3 个方法
# ============================================================

class Storage(ABC):
    """Event Store 抽象接口

    极简设计: 4 个抽象方法 + health()。

    This is the seam (Feathers). Adapters implement it.
    Pipeline depends on this ABC, never on concrete adapters.

    Tenant isolation: each adapter instance owns exactly one
    data directory / database / bucket. Corruption in one tenant's
    adapter MUST NOT affect other tenants.

    Subclass contract:
      - health() SHOULD return {"status": "ok" | "degraded", ...}
      - read_all() SHOULD tolerate corrupted records (skip + count)
      - append() MUST respect StorageCapability guard
    """

    @abstractmethod
    def append(self, event: Event, capability: StorageCapability | None = None) -> Event:
        """追加一条事件到 Event Store。

        Storage 负责:
          - 生成 event_id (UUID)
          - 设置 recorded_at (当前 UTC 时间)
          - 保证原子性写入
          - 验证 Capability（non-None 且 token 有效，否则拒写）

        Args:
            event: 业务代码创建的 Event (event_id 和 recorded_at 可为空)
            capability: Pipeline 授予的访问令牌

        Returns:
            同一个 Event 对象，event_id 和 recorded_at 已填充

        Raises:
            ArchitectureViolation: capability 缺失或无效
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
        """增量读取：从指定 event_id 之后开始读取"""
        ...

    @abstractmethod
    def health(self) -> dict:
        """Storage health report (required for all adapters)

        Returns {"status": "ok"|"degraded", ...}.
        Pipeline depends on this for Diagnostics.
        """
        ...

# Capability token seed: Pipeline 在 __init__ 时通过此 seed 创建 token，
# 注入 Storage。Token 检查是 O(1) hash 比较，不是 stack inspection。
_PIPELINE_CAPABILITY_SEED = "pipeline:{}"


def _validate_capability(capability: StorageCapability | None, expected_token: str):
    """O(1) token 验证 — 非 Pipeline 调用立即 Fail Fast"""
    if capability is None or not isinstance(capability._token, str):
        raise ArchitectureViolation(
            "Storage.append() 只能由 Pipeline 调用。"
            "检测到绕过 Pipeline 的直接写入。"
            "所有写入必须经过 InteractionPipeline.publish()。"
        )
    if capability._token != expected_token:
        raise ArchitectureViolation(
            "Storage capability token 不匹配。"
            "只有持有有效 token 的 Pipeline 才能写入。"
        )


class JSONLStorage(Storage):
    """append-only JSONL 实现 + WAL + Atomic Write

    Write path:
      1. 写 WAL entry (.wal)  — crash 后可恢复
      2. fsync WAL
      3. 写 events.jsonl
      4. fsync events.jsonl
      5. 清除 WAL

    Crash recovery:
      启动时检查 .wal 文件，如果有未提交 entry，replay 到 events.jsonl。

    Capability guard:
      append() 需要有效的 StorageCapability token。
    """

    def __init__(self, data_dir: str = "data", capability_token: str = ""):
        self.data_dir = data_dir
        self.log_file = os.path.join(data_dir, "events.jsonl")
        self.wal_file = os.path.join(data_dir, "events.jsonl.wal")
        self._capability_token = capability_token
        self._corrupted_records: int = 0
        os.makedirs(data_dir, exist_ok=True)
        # 启动时自动恢复
        self._recover_from_wal()

    # ---- WAL Recovery ----

    def _recover_from_wal(self) -> int:
        """从 WAL 恢复未提交的事件（crash recovery）

        启动时自动调用。如果 .wal 文件存在，将其中的事件
        append 到 events.jsonl，然后删除 .wal。

        Returns:
            恢复的事件数量
        """
        if not os.path.exists(self.wal_file):
            return 0

        recovered = 0
        try:
            with open(self.wal_file, "r", encoding="utf-8") as wal:
                with open(self.log_file, "a", encoding="utf-8") as log:
                    for line in wal:
                        line = line.strip()
                        if line:
                            log.write(line + "\n")
                            recovered += 1
                    log.flush()
                    os.fsync(log.fileno())
            # 成功恢复，删除 WAL
            os.remove(self.wal_file)
        except Exception:
            pass  # WAL 恢复失败不阻止启动，但保留 WAL 供下次尝试

        return recovered

    # ---- Capability ----

    def has_valid_capability(self, capability: StorageCapability | None) -> bool:
        """验证 capability token"""
        if capability is None:
            return False
        return capability._token == self._capability_token

    # ---- Atomic Write with WAL ----

    def append(self, event: Event, capability: StorageCapability | None = None) -> Event:
        """原子追加事件 — WAL → fsync → commit → fsync → clear WAL

        只有持有有效 StorageCapability 才能写入。
        """
        _validate_capability(capability, self._capability_token)

        # Storage 层负责生成 ID 和时间戳
        if not event.event_id:
            object.__setattr__(event, "event_id", str(uuid.uuid4()))
        if not event.recorded_at:
            object.__setattr__(event, "recorded_at", datetime.now(timezone.utc).isoformat())

        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"

        # Phase 1: Write WAL
        with open(self.wal_file, "w", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

        # Phase 2: Commit to main log
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

        # Phase 3: Clear WAL (write succeeded)
        if os.path.exists(self.wal_file):
            os.remove(self.wal_file)

        return event

    # ---- Read ----

    def read_all(self) -> Iterator[Event]:
        """逐条迭代所有事件，自动跳过损坏行"""
        if not os.path.exists(self.log_file):
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield Event.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError):
                    self._corrupted_records += 1
                    # 跳过损坏行，不中断整个读取
                    continue

    def read_since(self, event_id: str) -> Iterator[Event]:
        """增量读取：从指定 event_id 之后开始"""
        if not os.path.exists(self.log_file):
            return
        found = False
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = Event.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError):
                    self._corrupted_records += 1
                    continue
                if found:
                    yield event
                elif event.event_id == event_id:
                    found = True

    def count(self) -> int:
        """事件总数（跳过损坏行）"""
        if not os.path.exists(self.log_file):
            return 0
        count = 0
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    count += 1
                except (json.JSONDecodeError, KeyError, TypeError):
                    self._corrupted_records += 1
        return count

    # ---- Health ----

    def health(self) -> dict:
        """Storage Health Report — Unified HealthStatus schema

        Returns a dict with a guaranteed "status" field that conforms to:

            HealthStatus = Healthy | Warning | Degraded | Corrupted | Unavailable

        All callers (WebUI, CLI, MCP, Monitoring) consume only "status".
        Implementation details (wal_dirty, corrupted_records) are diagnostics-only.

        Returns:
            {
                "status": "healthy" | "warning" | "degraded" | "corrupted" | "unavailable",
                "current_size_bytes": int,
                "event_count": int,
                "corrupted_records": int,
                "wal_dirty": bool,
                "issues": [str],
            }
        """
        size = os.path.getsize(self.log_file) if os.path.exists(self.log_file) else 0
        total = self.count()
        wal_exists = os.path.exists(self.wal_file)

        status = "healthy"
        issues = []
        if wal_exists:
            status = "warning"
            issues.append("wal_dirty")
        if self._corrupted_records > 0:
            status = "degraded"
            issues.append("corrupted:{}".format(self._corrupted_records))

        return {
            "status": status,
            "current_size_bytes": size,
            "current_size_mb": round(size / (1024 * 1024), 2),
            "event_count": total,
            "corrupted_records": self._corrupted_records,
            "wal_dirty": wal_exists,
            "issues": issues,
        }

    def clear(self) -> None:
        """清空事件日志和 WAL（仅用于测试）"""
        for path in [self.log_file, self.wal_file]:
            if os.path.exists(path):
                os.remove(path)
        self._corrupted_records = 0
