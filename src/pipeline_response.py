"""PipelineResponse — ADR-010 实现

Pipeline.recall() 返回 PipelineResponse，不是裸 ContextObject。

v0.5: metadata + diagnostics 可空，保留扩展点。
v0.6: metadata.event_count 填充。
v0.7: metadata 完整填充（timing, trace, strategy）。
      diagnostics 首次填充（health, projections_summary, warnings）。
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Any
from .protocol import ContextObject


@dataclass
class RecallMetadata:
    """Recall 元数据 — Engine 的自我审计，不给 LLM 看"""
    version: int = 1
    engine_version: str = "v1.0"

    # Timing
    timing_ms: float = 0.0
    started_at: str = ""

    # Trace
    request_id: str = ""
    trace_id: str = ""

    # Strategy
    recall_strategy: str = "full_replay"
    scoring_method: str = "weighted_sum"
    cache_hit: bool = False
    snapshot_used: bool = False

    # Data
    event_count: int = 0
    total_events: int = 0
    person_count: int = 0

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "engine_version": self.engine_version,
            "timing_ms": round(self.timing_ms, 2),
            "started_at": self.started_at,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "recall_strategy": self.recall_strategy,
            "scoring_method": self.scoring_method,
            "cache_hit": self.cache_hit,
            "snapshot_used": self.snapshot_used,
            "event_count": self.event_count,
            "total_events": self.total_events,
            "person_count": self.person_count,
        }


@dataclass
class Diagnostics:
    """Recall 诊断信息 — Debug 时查看，不给 LLM 看

    v0.7: health + projections_summary + warnings
    """

    # Health snapshot
    storage: str = "healthy"
    dispatcher: str = "healthy"
    projection_count: int = 0
    registered_event_types: int = 0

    # Storage health
    storage_health: dict = field(default_factory=dict)

    # Per-projection timing
    projection_timing: dict[str, float] = field(default_factory=dict)

    # Warnings (non-fatal issues detected during recall)
    warnings: list[str] = field(default_factory=list)

    # Dead letter count from dispatcher
    dead_letter_count: int = 0

    # Version info
    engine_version: str = "v1.0"
    engine_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "health": {
                "storage": self.storage,
                "dispatcher": self.dispatcher,
                "projection_count": self.projection_count,
                "registered_event_types": self.registered_event_types,
            },
            "storage_health": self.storage_health,
            "projection_timing": {
                name: round(ms, 3)
                for name, ms in self.projection_timing.items()
            },
            "warnings": self.warnings,
            "dead_letter_count": self.dead_letter_count,
            "engine_version": self.engine_version,
            "engine_time": self.engine_time,
        }


@dataclass
class PipelineResponse:
    """Pipeline.recall() 的唯一返回类型

    ADR-010: Freeze API Shape, Grow Internal Capability.

    context:      ContextObject — 给 PromptAdapter / LLM（frozen API Contract）
    metadata:     RecallMetadata — Engine 自我审计
    diagnostics:  Diagnostics — Debug 信息（v0.7 起完整填充）

    调用方:
      response.context       → 只需要上下文的人
      response.metadata      → 需要了解召回过程的人
      response.diagnostics   → Debug 或运维时查看
    """
    context: ContextObject
    metadata: RecallMetadata
    diagnostics: Diagnostics | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "context": self.context.to_dict(),
            "metadata": self.metadata.to_dict(),
        }
        if self.diagnostics:
            d["diagnostics"] = self.diagnostics.to_dict()
        return d
