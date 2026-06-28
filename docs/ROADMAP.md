# Relationship OS — Roadmap

> Vision 是梦想，Roadmap 是路线。打开这一个文件就知道项目在哪。

---

## Phase 0: Foundation（已完成 ✅）

- [x] 架构讨论 + ADR (5 decisions)
- [x] ARCHITECTURE_PRINCIPLES.md (7 principles)
- [x] Context Contract v1 (4 must blocks + 2 optional)
- [x] Event Schema
- [x] Projection Interface
- [x] Storage Interface
- [x] Git + GitHub

**Completed: 2026-06-27**

---

## Phase 1: Protocol（统一语言）

```
目标: 所有模块说同一种语言
进度: 0%
```

- [ ] `ContextObject` dataclass (Identity / Memory / Relationship / Time / Emotion / System)
- [ ] `Event` schema 固化 (id / timestamp / source / type / payload)
- [ ] `Projection` interface 统一 (apply / update / output)
- [ ] `Storage` interface 统一 (append / read_since / snapshot / restore)

---

## Phase 2: Pipeline（最小闭环）

```
目标: 一条 Event 完整流过整个系统
进度: 0%
```

- [ ] `InteractionPipeline` (publish / recall / snapshot / rebuild)
- [ ] `ProjectionDispatcher` (register / dispatch / snapshot_all)
- [ ] `ContextComposer` (筛选 → 排序 → 摘要 → 压缩)
- [ ] `Snapshot` (定期保存 Projection 快照)
- [ ] 端到端验证: 一句话跑通全链路

---

## Phase 3: Projection Ecosystem

```
目标: 新 Projection = 一行注册, 不改 Pipeline
进度: 0%
```

- [ ] FactProjection (已有基础)
- [ ] PersonProjection (已有基础)
- [ ] RelationshipProjection (已有基础)
- [ ] TimeContextProjection (已有基础)
- [ ] EmotionProjection (已有基础)
- [ ] GrowthProjection (已有基础)
- [ ] ReminderProjection (已有基础)
- [ ] ConversationProjection (已有基础)
- [ ] TimelineProjection (新建)
- [ ] GoalProjection (新建)

---

## Phase 4: Adapter + Storage

```
目标: 多模型 + 高性能存储
进度: 0%
```

- [ ] Prompt Adapter (Claude / GPT / Gemini / DeepSeek)
- [ ] Storage 切换 (JSONL → SQLite，不改业务代码)
- [ ] Incremental Projection (百万级事件)
- [ ] Memory Compaction (压缩旧事件)

---

## Future（远期规划）

```
Phase 5: Intelligence
  □ Semantic Search (embedding)
  □ Memory Reasoner (推断)
  □ Proactive Memory (主动提醒)
  □ Emotion Engine (情绪分析)
  □ Relationship Engine (关系演化)

Phase 6: Interaction
  □ Plugin System
  □ MCP Server v2
  □ WebUI v2 (React)
  □ Voice Input / Output
  □ Multi-modal Support

Phase 7: Platform
  □ Multi-user
  □ Multi-device sync
  □ Social Graph
  □ Community Edition
  □ Mobile App

Phase 8: Beyond
  □ AR / Hologram
  □ Brain-Computer Interface
  □ ...
```

---

## Milestones

| Tag | 内容 | 状态 |
|-----|------|------|
| v0.3.95 | FactProjection + 32 tests | ✅ |
| v0.3.99 | Architecture Review (10 docs + 7 principles + 5 ADR) | ✅ |
| v0.4 | Phase 1+2: Protocol + Pipeline 最小闭环 | 📋 |
| v0.5 | Phase 3: Projection Ecosystem | 📋 |
| v0.6 | Phase 4: Adapter + Storage | 📋 |
| v1.0 | Relationship OS MVP | 🎯 |

---

*每个 Phase 完成后，打 GitHub Release。*
*每完成一个 Phase，回来更新这个文件。*
