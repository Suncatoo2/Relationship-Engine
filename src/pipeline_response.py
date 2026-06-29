"""PipelineResponse — ADR-010 最小实现

Pipeline.recall() 返回 PipelineResponse，不是裸 ContextObject。
v0.5: metadata + diagnostics 可空，保留扩展点。
v0.6+: 逐步填充 metadata (scoring / strategy / latency)
"""

from dataclasses import dataclass, field
from .protocol import ContextObject


@dataclass(frozen=True)
class RecallMetadata:
    """Recall 元数据 — Engine 的自我审计，不给 LLM 看"""
    version: int = 1
    engine_version: str = "v0.5"
    recall_strategy: str = "full_replay"
    scoring_method: str = "weighted_sum"
    cache_hit: bool = False
    snapshot_used: bool = False
    event_count: int = 0
    retrieval_latency: float = 0.0


@dataclass
class PipelineResponse:
    """Pipeline.recall() 的唯一返回类型

    ADR-010: Freeze API Shape, Grow Internal Capability.

    context:      ContextObject — 给 PromptAdapter / LLM（frozen API Contract）
    metadata:     RecallMetadata | None — Engine 自我审计（v0.5 可空）
    diagnostics:  dict | None — Debug 信息（v0.5 占位，可空）

    调用方:
      response.context       → 只需要上下文的人
      response.metadata      → 需要了解召回过程的人
      response.diagnostics   → Debug 时才看（v0.5 永远为 None）
    """
    context: ContextObject
    metadata: RecallMetadata | None = None
    diagnostics: dict | None = None
