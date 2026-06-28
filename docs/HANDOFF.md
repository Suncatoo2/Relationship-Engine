# Project Handoff — Relationship Event OS

> **给下一位 Claude（以及未来的自己）**
> 读完这份文档，你应该能完全理解项目现状并直接开始开发。不需要重新讨论架构。

---

## 1. 项目身份

- **产品名**: Relationship OS
- **仓库**: https://github.com/Suncatoo2/Relationship-Engine
- **核心理念**: 创造一个能够和人一起经历时间的 AI
- **核心架构**: Everything is Event, Everything else is Projection
- **当前版本**: v0.5-context-filled (Development Milestone)
- **下一版本**: v0.4.0-infrastructure (Architecture Release)

---

## 2. 已完成工作

### 2.1 架构设计

| 文档 | 位置 |
|------|------|
| 项目 Vision | `docs/VISION.md` |
| 项目 Roadmap | `docs/ROADMAP.md` |
| 架构原则 (7 Principles) | `docs/architecture/ARCHITECTURE_PRINCIPLES.md` |
| 架构决策记录 (6 ADR) | `docs/architecture/ARCHITECTURE_DECISIONS.md` |
| Pipeline Architecture | `docs/architecture/01_pipeline_architecture.md` |
| Interaction Pipeline | `docs/architecture/INTERACTION_PIPELINE.md` |
| Storage Abstraction | `docs/architecture/STORAGE_ABSTRACTION.md` |
| Projection Snapshot | `docs/architecture/PROJECTION_SNAPSHOT.md` |
| Memory Lifecycle | `docs/architecture/MEMORY_LIFECYCLE.md` |
| Refactor Roadmap | `docs/architecture/REFACTOR_ROADMAP.md` |
| Step 4 Design | `docs/architecture/STEP4_DESIGN.md` |

### 2.2 已完成代码

| 功能 | 位置 | 状态 |
|------|------|------|
| **Pipeline**（37 行，只做协调） | `src/interaction_pipeline.py` | ✅ |
| **Dispatcher**（registry 模式） | `src/dispatcher.py` | ✅ |
| **Storage**（ABC + JSONLStorage） | `src/storage.py` | ✅ |
| **ContextComposer**（5 Projections → ContextObject） | `src/context_composer.py` | ✅ |
| **MemoryReasoner**（summary + highlights） | `src/memory_reasoner.py` | ✅ |
| **Event Schema**（version/occurred_at/recorded_at） | `src/event_types.py` | ✅ |
| **ContextObject**（4+2 blocks + version check） | `src/protocol.py` | ✅ |
| 8 个 Projection | `src/projections/` | ✅ |
| web_server（接入 Pipeline） | `src/web_server.py` | ✅ |
| mcp_server（未接入 Pipeline） | `src/mcp_server.py` | ❌ |

### 2.3 测试

| 类型 | 数量 | 状态 |
|------|------|------|
| 单元测试 | 294 | ✅ |
| Memory Test Suite | 32 | ⚠️ 需适配新 API |
| 验收测试 | 47 | ⚠️ 需适配新 API |
| Protocol 测试 | 10 | ✅ |

### 2.4 Git 状态

```
Development Milestones: v0.3-stable, v0.4-pipeline, v0.5-context-filled
Architecture Releases:  待打 v0.4.0-infrastructure
分支: main
待推送: 网络恢复后 push origin main --tags
```

---

## 3. 7 条架构原则（不可违反）

1. **Engine 永远不思考** — Engine 是确定性管道，不做推理/猜情绪
2. **LLM 永远负责推理** — 理解/判断/提取事实全部是 LLM 的事
3. **Projection 必须纯函数** — `project(events) → Profile (frozen)`, 无状态
4. **Storage 可以替换** — 业务代码不直接读写文件，走 Storage 接口
5. **Context Object 是唯一输出** — Memory Engine 输出结构化 Object，非文本
6. **Snapshot 只是缓存** — 不替 Event Log，可从 Event Log 重建
7. **Event 永远不可修改** — append-only, 算错了就重新 replay

---

## 4. 6 条 ADR（已经决定，不要重新讨论）

1. **ADR-001**: Everything is Event
2. **ADR-002**: Projection 必须 Stateless + Immutable
3. **ADR-003**: Engine never competes with LLM for thinking
4. **ADR-004**: Storage 必须抽象
5. **ADR-005**: 高层只有一个入口 — publish_interaction()
6. **ADR-006**: Pipeline 铁律 — 只有 Pipeline 可以访问 Event Store

---

## 5. 架构铁律（Phase 1 确立，不可违反）

1. **架构冻结**: 不再新增核心抽象，新想法进 ROADMAP 或 ADR
2. **ADR First**: 涉及架构调整时先写 ADR 再改代码
3. **IO 隔离**: Pipeline 不直接操作文件或数据库
4. **Projection 铁律**: 任何 Projection 都不能主动读 Event Store
5. **Pipeline 不超 150 行**: 只做协调，不负责实现

---

## 6. 当前数据流

```
用户输入
    │
    ▼
InteractionPipeline.publish(interaction)   ← 唯一写入口
    │
    ├── decompose(interaction) → [Event]
    ├── Storage.append(event) × N
    └── Dispatcher.dispatch(event) × N
            │
            └── registry[event.type] → [Projection.apply(event)]

Pipeline.recall(person)                    ← 唯一读出口
    │
    ├── Storage.read_all()
    ├── Dispatcher.project_all(events)
    └── ContextComposer.compose(person, events, profiles)
            │
            └── ContextObject JSON
```

---

## 7. v0.4.0-infrastructure 交付清单

| # | 交付物 | 状态 |
|---|--------|------|
| 1 | Pipeline（publish/recall） | ✅ |
| 2 | Dispatcher（registry 模式） | ✅ |
| 3 | BaseStorage + JSONLStorage（含 read_since） | ⚠️ read_since 待加 |
| 4 | Event Schema（version/occurred_at/recorded_at） | ✅ |
| 5 | ContextObject（冻结 + GoalsBlock） | ⚠️ GoalsBlock 待加 |
| 6 | Snapshot 基础接口 | ✅ |
| 7 | web_server 接入 Pipeline | ✅ |
| 8 | mcp_server 接入 Pipeline（读写统一） | ❌ 待做 |
| 9 | 测试体系升级 | ❌ 待做 |

### 验收标准

```
Write: LLM → publish_interaction() → Pipeline → Storage → Dispatcher
Read:  LLM → get_context(person)   → Pipeline → ContextObject JSON
红线:  LLM 不再感知 Storage 和 EventLog 的存在
```

---

## 8. 伏笔 & 技术债（已确认，按优先级排列）

| # | 伏笔 | 建议时机 |
|---|------|---------|
| 1 | mcp_server 接入 Pipeline | v0.4.0 |
| 2 | JSONLStorage read_since | v0.4.0 |
| 3 | ContextObject 加 GoalsBlock | v0.4.0 |
| 4 | memory_summary 填充 | v0.5.0 |
| 5 | category="goal" 验证 | v0.5.0 |
| 6 | 7 个 Projection 补 apply()/snapshot() | v0.5.0 |
| 7 | PromptAdapter 抽象接口 | v0.6.0 |
| 8 | Snapshot 持久化 + Incremental | v0.7.0 |
| 9 | Goal Projection 独立拆分 | v0.6.0+ |
| 10 | 异步 Dispatcher | v0.7.0+ |
| 11 | Outbox Pattern | v0.7.0+ |

---

## 9. 接手后第一件事

```bash
# 1. 读架构文件
cat docs/ROADMAP.md
cat docs/architecture/ARCHITECTURE_DECISIONS.md

# 2. 跑测试
python -m pytest tests/ --ignore=tests/acceptance_test.py --ignore=tests/test_memory_suite.py -q

# 3. 验证 Pipeline 能运行
python -c "from src.interaction_pipeline import InteractionPipeline; print('OK')"

# 4. 继续 v0.4.0-infrastructure
#   下一步: mcp_server 接入 Pipeline（读写统一）
```

---

*Handoff 更新时间: 2026-06-28*
*最后 tag: v0.5-context-filled (Development Milestone)*
*下一版本: v0.4.0-infrastructure (Architecture Release)*
