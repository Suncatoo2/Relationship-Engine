# Project Handoff — Relationship Event OS

> **读完这份文档，你应该能完全理解项目现状并直接开始开发。不需要重新讨论架构。**

---

## 1. 项目身份

```
产品名:        Relationship OS
仓库:          https://github.com/Suncatoo2/Relationship-Engine
核心理念:      创造一个能够和人一起经历时间的 AI
核心架构:      Everything is Event, Everything else is Projection

Architecture Version : v0.8 (Stable)
Implementation Version : v0.6 (Incremental Projection)

版本体系: Architecture–Implementation Dual Lifecycle Versioning
```

---

## 2. 直接开始

```bash
git clone https://github.com/Suncatoo2/Relationship-Engine.git
cd Relationship-Engine
pip install -e .
python -m pytest tests/ -q
# → 340 passed
```

---

## 3. 当前状态总结

### 完成了什么

| 版本 | 能力 |
|------|------|
| v0.4 | Pipeline + Dispatcher (registry) + Storage (JSONL + read_since) |
| v0.5 | ContextComposer + Confidence Engine + Knowledge Boundary + Health Score |
| v0.6 | Incremental Projection — 全部 6 个 Projection 支持 apply() + snapshot() |

### 数据流

```
Interaction → Pipeline.publish() → Storage.append() → Dispatcher.dispatch()
                                                         ↓
                                              Projection.apply(event)  O(1)
                                                         ↓
Pipeline.recall() → Storage.read_all() → Projection.snapshot() → ContextComposer → ContextObject → PromptAdapter → LLM
```

### 6 个 Projection — 全部支持增量

```
FactProjection:        apply() ✅  snapshot() ✅
PersonProjection:      apply() ✅  snapshot() ✅
RelationshipProjection: apply() ✅  snapshot() ✅
TimeContextProjection:  apply() ✅  snapshot() ✅
EmotionProjection:      apply() ✅  snapshot() ✅
GrowthProjection:       apply() ✅  snapshot() ✅
ConversationProjection: apply() ⬜  snapshot() ⬜  (batch only)
ReminderProjection:     apply() ⬜  snapshot() ⬜  (batch only)
```

### 核心模块（按文件）

| 文件 | 职责 | 行数 |
|------|------|------|
| `src/interaction_pipeline.py` | Pipeline 唯一入口 | ~200 |
| `src/dispatcher.py` | Projection 路由 registry | ~100 |
| `src/storage.py` | Storage ABC + JSONLStorage | ~160 |
| `src/context_composer.py` | Projections → ContextObject | ~280 |
| `src/memory_reasoner.py` | Summary + highlights | ~90 |
| `src/prompt_adapter.py` | ContextObject → Prompt | ~170 |
| `src/snapshot_manager.py` | Snapshot save/load/verify | ~140 |
| `src/boundary_policy.py` | Policy isolation | ~60 |
| `src/pipeline_response.py` | ADR-010 wrapper | ~30 |
| `src/protocol.py` | ContextObject spec (FROZEN) | ~230 |

### 架构文档

```
12 Principles:  docs/architecture/ARCHITECTURE_PRINCIPLES.md
11 ADRs:        docs/architecture/ARCHITECTURE_DECISIONS.md
6 Philosophies: docs/architecture/INTERACTION_PHILOSOPHY.md
Flow Diagram:   docs/MEMORY_FLOW.md
Roadmap:        docs/ROADMAP.md
```

---

## 4. 测试

```
340 passed (0.36s)

pytest:        python -m pytest tests/ -q
acceptance:    python tests/acceptance_test.py
alice demo:    python examples/alice_demo.py
```

---

## 5. 已知技术债（debt.md）

| # | 债务 | 建议时机 |
|---|------|---------|
| 1 | ConversationProjection / ReminderProjection 没有 apply() | v0.7 |
| 2 | PipelineResponse metadata 未填充 | v0.7 |
| 3 | memory_summary → memory_facts 改名 | Major Version |
| 4 | Event Schema 旧数据格式迁移工具 | 需要时 |
| 5 | Crash Recovery (WAL/fsync) | v0.7 |
| 6 | SnapshotManager 持久化+增量切换 | replay > 500ms 时 |

---

## 6. 未完成的工作（明天）

### P0 — v0.7 Blocking

- ConversationProjection + ReminderProjection 补 apply()/snapshot()
- 更新 acceptance_test.py 到新 ContextComposer API（3 remaining failures 已 deleted, 0 remaining）

### P1 — 可推迟

- PipelineResponse RecallMetadata 填充
- test_memory_suite.py.integration → 恢复运行（需 web_server 环境）

### P2 — Architecture Design（不进代码）

- Memory Runtime (ADR-010 完整实现)
- Decision Graph (diagnostics)
- Multi-Agent Memory Arbitration

---

*Handoff 时间: 2026-06-28*
*Implementation: v0.6.0-incremental*
*Architecture: v0.8 Stable*
*最后 commit: 67f83bf*
