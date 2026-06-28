# ADR-010: PipelineResponse Protocol

**日期：** 2026-06-28
**状态：** Accepted (Architecture: v0.8. Implementation: deferred to v0.4+)

---

## 决策

Pipeline.recall() 返回 `PipelineResponse`，不是 Tuple。

```python
PipelineResponse
  ├── context: ContextObject            # Frozen API Contract → PromptAdapter / LLM
  ├── metadata: RecallMetadata | None   # Explainability / UI / Observability
  └── diagnostics: Diagnostics | None   # Debug（可选，可关闭）
```

## 原因

1. **API Extensibility** — 新增字段不影响已有调用方。Tuple 会随字段增长而脆弱。
2. **Separation of Concerns** — ContextObject 只含业务事实，metadata 是 Engine 元信息。
3. **Freeze API Shape, Grow Internal Capability** — 接口先行冻结，实现逐步填充。

## Metadata 分层（Metadata Layering）

```
Engine Metadata
  recall_strategy:    "semantic" | "temporal" | "relationship" | "full_replay"
  retrieval_latency:  0.012  (seconds)
  scoring_method:     "weighted_sum"
  cache_hit:          false
  snapshot_used:      true | false

Pipeline Metadata
  replay_mode:        "incremental" | "full" | "degraded"
  snapshot_id:        "abc-123" | null
  degraded_mode:      false
  event_count:        42

Product Metadata (future)
  relationship_insight: "..."
  timeline_analytics:   "..."
```

## 生命周期（Lifecycle）

```
ContextObject     → 长期存在（frozen contract）
RecallMetadata    → 可缓存、可持久化、可关闭
Diagnostics       → 一次请求结束即可销毁
```

## Feature Flag

```
Pipeline(enable_metadata=False, enable_diagnostics=False)
# 企业部署: 只需要 Context，关闭一切元数据
# Debug 模式: 全部打开
```

## Error Boundary（错误边界）

```
Metadata 获取失败 → ContextObject 正常返回 → LLM 正常工作
Metadata 永远属于辅助信息，不是核心流程。
```

## LLM Zero Knowledge（零认知原则）

```
Metadata 永远属于 Engine。
PromptAdapter 永远只看 ContextObject。

禁止: LLM 根据 score 推理
禁止: LLM 根据 latency 判断
禁止: LLM 根据 strategy 改 Prompt

Engine 决策，LLM 表达。ADR-007 的核心。
```

## 版本兼容

```python
@dataclass(frozen=True)         # immutable — 生成后不可变，保证可复现
class RecallMetadata:
    version: int = 1             # scoring 版本：Keyword(1) → Embedding(2) → Graph(3)
    engine_version: str = "v0.8" # Engine 版本，用于追溯
    recall_strategy: str = ""
    retrieval_latency: float = 0.0
    scoring_method: str = ""
    cache_hit: bool = False
    snapshot_used: bool = False
    event_count: int = 0
```

**Immutable** — Metadata 一旦生成就不可变。任何 Debug 都能得到完全一致的解释结果（Reproducibility）。

**engine_version** — 未来 Scoring 公式从 Keyword → Embedding → Graph 演进时，历史 Metadata 仍可追溯。"这个 score=0.85 是 v0.8 的 Keyword 公式算的，不是 v2.0 的 Graph 公式"。

## 序列化

```python
response.to_json() → str
PipelineResponse.from_json(s) → PipelineResponse
# 未来: 网络通信、MCP、Agent、Remote Engine
```

## 插件扩展（Plugin Extension）

```python
metadata.extensions 或 metadata.plugins
# 禁止直接塞字段。统一扩展入口，避免字段爆炸。
```

## 实现路径

```
v0.8 Architecture: 设计完整（本文档）
v0.4+ Implementation:
  PipelineResponse 只含 context（metadata + diagnostics 为 None）
v0.5+ Implementation:
  逐步填充 metadata（scoring / strategy / latency）
v1.0+ Implementation:
  完整填充 + Debug Dashboard
```

## 后果

- Pipeline.recall() 不再返回裸 ContextObject，而是 PipelineResponse
- 已有调用方（web_server / mcp_server）需要访问 `response.context`（一行改动）
- Metadata 和 Diagnostics 默认 None，不开功能则零开销
- 与 ADR-007（Engine Detects, LLM Explains）完全一致——Metadata 是 Engine 的自我审计，不是 LLM 的输入
