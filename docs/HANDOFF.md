# Project Handoff — Relationship Event OS

> **给下一位 Claude（以及未来的自己）**
> 读完这份文档，你应该能完全理解项目现状并直接开始开发。不需要重新讨论架构。

---

## 1. 项目身份

```
产品名:        Relationship OS
仓库:          https://github.com/Suncatoo2/Relationship-Engine
核心理念:      创造一个能够和人一起经历时间的 AI
核心架构:      Everything is Event, Everything else is Projection

Architecture Version : v0.8 (Stable)
Implementation Version : v0.4 (In Progress)

版本体系: Architecture–Implementation Dual Lifecycle Versioning
          架构有自己的演进速度，实现有自己的开发速度
```

---

## 2. 架构全景

### 12 条架构原则

```
 1. Engine 永远不思考
 2. LLM 永远负责推理
 3. Projection 必须纯函数
 4. Storage 可以替换
 5. Context Object 是唯一输出
 6. Snapshot 只是缓存
 7. Event 永远不可修改
 8. Engine Detects, LLM Explains
 9. Identity-Aware, Authentication-Agnostic
10. Engine Emits Facts, Never Narratives
11. Architecture First, Implementation Incrementally
12. Future Complexity, Present Simplicity
```

### 11 个 ADR

```
ADR-001  Everything is Event
ADR-002  Projection Stateless + Immutable
ADR-003  Engine never competes with LLM
ADR-004  Storage 抽象
ADR-005  publish_interaction() 唯一入口
ADR-006  Pipeline 铁律 + Event Schema
ADR-007  Engine Detects, LLM Explains
ADR-008  Interaction Philosophy (6 principles)
ADR-009  Memory Retrieval Policy
ADR-010  PipelineResponse Protocol
ADR-011  Architecture Evolution Policy
```

### 6 条交互哲学

```
1. Memory should be demonstrated, never announced.
2. Memory should feel acknowledged, not announced.
3. Show, don't tell.
4. Suggestions are intents, not commands.
5. Engine outputs facts, not derivations.
6. PromptAdapter outputs constraints, not prose.
```

### Architecture Manifesto

> Relationship OS is not a memory library — it is an AI interaction operating system. The Engine owns facts and decisions; the LLM owns expression. Every new capability must preserve this separation.

---

## 3. 当前数据流

```
用户输入 (Interaction)
    │
    ▼
InteractionPipeline.publish()          ← 唯一写入口
    │
    ├── Storage.append(event)          ← 不可变 Event Log (data/{user_id}/events.jsonl)
    └── Dispatcher.dispatch(event)     ← registry 模式路由
            │
            ▼
Projection Layer (6 个)
  Fact / Person / Relationship / Time / Emotion / Growth
            │
            ▼
ContextComposer
  ├── MemoryReasoner (summary)
  ├── Suggestions (Engine Detects)
  └── ContextObject (frozen API Contract, 4+2+1 blocks + suggestions)
            │
            ▼
PromptAdapter (Claude / GPT / DeepSeek)
            │
            ▼
LLM / 离线回复
```

---

## 4. 已完成架构设计（Architecture Milestones）

| 版本 | 设计内容 | 状态 |
|------|---------|------|
| v0.4 | Infrastructure — Pipeline + Dispatcher + Storage + Event Schema | ✅ |
| v0.5 | Memory Core — ContextComposer + Reasoner + Golden Context + Goals | ✅ |
| v0.6 | Output Layer — PromptAdapter + Lifecycle + Momentum + Suggestions | ✅ |
| v0.7 | Performance — SnapshotManager + Incremental + Recovery | ✅ |
| v0.8 | PipelineResponse + RecallMetadata + Evolution Policy + Manifesto | ✅ |

---

## 5. 已完成代码实现（Implementation Status）

### 核心模块全部存在

| 模块 | 文件 | 行数 | 状态 |
|------|------|------|------|
| Pipeline | `src/interaction_pipeline.py` | ~200 | ✅ |
| Dispatcher | `src/dispatcher.py` | ~100 | ✅ |
| Storage | `src/storage.py` | ~140 | ✅ |
| ContextComposer | `src/context_composer.py` | ~250 | ✅ |
| MemoryReasoner | `src/memory_reasoner.py` | ~90 | ✅ |
| PromptAdapter | `src/prompt_adapter.py` | ~170 | ✅ |
| SnapshotManager | `src/snapshot_manager.py` | ~120 | ✅ |
| ContextObject | `src/protocol.py` | ~200 | ✅ Frozen |
| 6 Projections | `src/projections/` | — | ✅ |

### 主链路已接通

```
✅ web_server → pipeline.publish() — 零直接 append
✅ web_server → memory_engine.recall() → PromptAdapter → 回复文本
✅ memory_engine → PromptAdapter.build(ctx) — 不再硬编码 prompt_text
✅ Snapshot 自动保存 — 每 100 次写入触发
✅ mcp_server → Pipeline — 读写统一
```

### 测试

```
344 pytest passed（不含已跳过文件）
315 pytest passed（排除 deprecated 文件后）
acceptance_test: 44/47 passed（3 fail = 旧 ContextComposer API）
```

---

## 6. 未完成工作（明天继续）

### 优先级 P0（必须做）

| # | 任务 | 说明 |
|---|------|------|
| 1 | **acceptance_test.py 修复最后 3 个失败** | `composer.compose()` 旧 API → 需要适配新 ContextComposer |
| 2 | **test_context_composer.py 适配** | 全部使用旧 ContextComposer API，需要迁移 |
| 3 | **test_prompt_builder.py 替代** | 用 test_prompt_adapter.py 替代（已存在 20 tests） |
| 4 | **test_memory_suite.py 恢复** | 32 个测试依赖启动 web_server 的完整环境 |

### 优先级 P1（应该做）

| # | 任务 | 说明 |
|---|------|------|
| 5 | **`event_log.py` 删除** | 零业务引用，safe to remove |
| 6 | **`memory_selector.py` FactItem 去重** | 与 protocol.py 的 FactItem 冲突 |
| 7 | **`context.py` 删除** | deprecated，换成 context_composer.py（但需先修 acceptance_test） |
| 8 | **`prompt_builder.py` 删除** | deprecated，换成 prompt_adapter.py（但需先修 acceptance_test） |

### 优先级 P2（可以推迟）

| # | 任务 | 说明 |
|---|------|------|
| 9 | PromptAdapter 语气阶梯接入 web_server | `_tone_for_stage()` 代码存在但离线模式没用 |
| 10 | Emotion Momentum + Lifecycle 在 UI 展示 | 计算了但没人看 |
| 11 | PipelineResponse + RecallMetadata 实现 | ADR-010 设计了但代码没写 |
| 12 | `data/` 目录 cleanup | 旧 events.jsonl 是旧格式 `id`/`timestamp`，新格式是 `event_id`/`occurred_at` |

---

## 7. 今天犯过的错 & 教训

| 错误 | 修复 | 教训 |
|------|------|------|
| acceptance_test.py 用旧 `EventLog` → NameError | 全局替换为 `JSONLStorage` | 全局重构时先 grep 所有引用 |
| `context.py` incomplete edit → SyntaxError | 重读文件，用 exact string 再替换 | Edit 工具要求 old_string 精确匹配 |
| `person` 参数不传 → Alice/Bob 数据污染 | Dispatcher.project_all() 加 `person=` 参数 | Projection 的 `project(events, person="")` 必须传 |
| memory_engine 硬编码 prompt_text → PromptAdapter 未接入 | 替换为 `self._adapter.build(ctx)` | 新模块要接上调用方，否则是 dead code |
| acceptance_test `budget_limit` 参数 → TypeError | 新 ContextComposer 没有此参数，skip 旧代码 | 旧 API 迁移需要文档记录 |

---

## 8. 关键文件索引

| 文件 | 作用 | 状态 |
|------|------|------|
| `src/interaction_pipeline.py` | Pipeline 唯一入口 | ✅ Thin (37 lines core) |
| `src/dispatcher.py` | Projection 路由 | ✅ Registry pattern |
| `src/storage.py` | Storage ABC + JSONLStorage | ✅ read_since 已加 |
| `src/context_composer.py` | Projections → ContextObject | ✅ 6 blocks |
| `src/memory_engine.py` | PromptAdapter 调用层 | ✅ Wired |
| `src/prompt_adapter.py` | ContextObject → Prompt | ✅ 3 adapters |
| `src/snapshot_manager.py` | Snapshot save/load | ✅ Auto save wired |
| `src/protocol.py` | ContextObject spec | ✅ Frozen |
| `docs/architecture/ARCHITECTURE_PRINCIPLES.md` | 12 条原则 | ✅ |
| `docs/architecture/ARCHITECTURE_DECISIONS.md` | 11 个 ADR | ✅ |
| `docs/architecture/INTERACTION_PHILOSOPHY.md` | 6 条交互哲学 | ✅ |
| `docs/architecture/ADR-010-pipeline-response.md` | PipelineResponse 设计 | ✅ |
| `docs/architecture/ADR-011-evolution-policy.md` | 演进策略 | ✅ |
| `docs/ROADMAP.md` | 路线图 | ✅ Updated |
| `docs/MEMORY_FLOW.md` | 数据流图 | ✅ |
| `examples/alice_demo.py` | 端到端演示 | ✅ |

---

## 9. 明天第一件事

```bash
# 1. 验证当前状态
cd Relationship-Engine
python -m pytest tests/ --ignore=tests/test_memory_suite.py --ignore=tests/test_context_composer.py --ignore=tests/test_prompt_builder.py -q
# 应返回: 315 passed

# 2. Architecture Freeze 仍然生效
#    不再新增 ADR。只写代码。

# 3. 修复 P0 项（按顺序）:
#    a. acceptance_test.py 最后 3 个失败
#    b. test_context_composer.py 适配
#    c. test_memory_suite.py 恢复

# 4. 完成后打 tag:
#    git tag v0.4.0-implementation-complete
#    git push origin main --tags
```

---

*Handoff 更新时间: 2026-06-28*
*Architecture Version: v0.8 Stable*
*Implementation Version: v0.4 → v0.6 Wired*
*最后 commit: 7e7a73d (integration sprint)*
