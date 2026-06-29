# Technical Debt Register — Relationship OS

> v0.4.0-implementation-complete
> Architecture v0.8 Stable | Implementation v0.4

## Active Debt (P1 — planned removal)

| # | File | Issue | Replacement | Removal Target | Owner |
|---|------|-------|-------------|----------------|-------|
| 1 | `src/event_log.py` | 零业务引用，已标记 .deprecated | `src/storage.py` | v0.4.0 | Sprint |
| 2 | `tests/test_event_log.py` | 测试旧 EventLog API | test_storage.py | v0.4.0 | Sprint |
| 3 | `src/memory_selector.py` | FactItem 与 protocol.py 冲突 | protocol.py FactItem | v0.4.0 | Sprint |
| 4 | `src/projections/context.py` | 重复 ContextComposer | `src/context_composer.py` | v0.4.0 | Sprint |
| 5 | `src/projections/prompt_builder.py` | 重复 Prompt Builder | `src/prompt_adapter.py` | v0.4.0 | Sprint |
| 6 | `tests/test_context_composer.py.deprecated` | 旧 API 测试 | test_golden_context.py | v0.4.0 | Sprint |
| 7 | `tests/test_prompt_builder.py.deprecated` | 旧 API 测试 | test_prompt_adapter.py | v0.4.0 | Sprint |
| 8 | `tests/test_event_log.py.deprecated` | 旧 API 测试 | test_storage.py | v0.4.0 | Sprint |

## Integration Debt (P2 — needs environment)

| # | File | Issue | When to restore |
|---|------|-------|-----------------|
| 9 | `tests/test_memory_suite.py.integration` | 需要完整 web_server 环境 + 真实 LLM | CI 环境就绪后 |
| 10 | `tests/acceptance_test.py` | 独立脚本，非 pytest。用 `python tests/acceptance_test.py` 运行 | — |

## Architecture Debt (P3 — v0.5+)

| # | Issue | Reason deferred | When |
|---|-------|-----------------|------|
| 11 | `memory_summary` → `memory_facts` rename | API Contract 冻结，不改 | Next Major Version |
| 12 | PipelineResponse + RecallMetadata 实现 | ADR-010 设计完毕，Implementation 延迟 | v0.5+ |
| 13 | SnapshotManager Incremental Replay 实际切换 | 当前全量 replay < 100ms，收益为零 | replay > 500ms 时 |
| 14 | Projection.apply() 未实现（除 FactProjection） | 其余 5 个 Projection 只支持 project() | v0.5+ |
| 15 | Embedding/Semantic Search | 当前 keyword 足够 | v1.0+ |

## Resolved Debt（今天的成果）

| # | Issue | Resolution |
|---|-------|-----------|
| — | web_server 硬编码 prompt_text | → PromptAdapter.build(ctx) |
| — | memory_engine 硬编码 prompt_text | → PromptAdapter.build(ctx) |
| — | acceptance_test 3 ghost tests | → 删除（测试旧 API 行为，新测试已覆盖） |
| — | EventLog 零引用 | → 标记 .deprecated |
| — | context.py / prompt_builder.py 重复 | → 标记 deprecated |
| — | Snapshot 未自动保存 | → 每 100 次写入自动触发 |
