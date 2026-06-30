# Relationship OS — Roadmap v3

> 最后更新：2026-06-30
> 当前版本：Engine 1.0 (Frozen) | Product 1.0 (Starting)

---

## Engine 1.0 — 冻结 (2026-06-30)

**目标：永远稳定。除非 Bug，不新增底层能力。**

### 交付物

| 类别 | 能力 | 状态 |
|------|------|------|
| Event Sourcing | Event Log (JSONL) + 8 Projections | ✅ |
| Pipeline | publish / recall / decompose | ✅ |
| Capability Guard | Token-based runtime enforcement | ✅ |
| Crash Recovery | WAL + Atomic Write + Recovery Replay | ✅ |
| Snapshot Integrity | Checksum + Schema Version + Rebuild | ✅ |
| Observability | trace_id, timing, health, warnings, dispatch_stats | ✅ |
| Contract Tests | 7 Pipeline Contract Tests, 29 Architecture Tests | ✅ |
| Coverage | 379 tests (0.6s) | ✅ |

### 冻结范围

以下内容 **不再修改**：
- Event schema (event_id, occurred_at, recorded_at, version, type, data, person, source)
- Pipeline 接口 (publish, recall, snapshot, rebuild)
- Storage 接口 (append, read_all, read_since, count)
- Projection 接口 (apply, snapshot, project)
- PipelineResponse 字段 (context, metadata, diagnostics)

以下内容 **可以修改**：
- 新增 Projection (不影响已有 8 个)
- 新增 EventType (不修改已有字段)
- Performance tuning (不改变接口语义)
- Bug fixes

---

## Product 1.0 — Pipeline（产品化路径）

**目标：让用户感受到"记忆的价值"，不是"数据库的存在"。**

### 产品化路径

```
ProfileProjection — 长期人格记忆层（不是调查问卷）
     ↓
TimelineProjection — 时间线可视化（关系如何随时间变化）
     ↓
RelationshipProfile — 关系档案（使已有 RelationshipProjection 变得可见）
     ↓
Memory Search — 记忆检索（让用户搜索 AI 记住了什么）
     ↓
Context Builder — 上下文可见（让用户看到 AI 当前知道什么）
     ↓
Web UI — 把以上全部变成界面
     ↓
真实用户 — 5-10 人连续使用，获取反馈
```

### 为什么 Context Builder 在 Memory Search 之后

ContextComposer（Context Builder 的引擎层）**已经存在**于 `src/context_composer.py`：

```
8 Projections → ContextComposer → ContextObject (8 Blocks) → PromptAdapter → LLM
```

所以 Product 1.0 的 Context Builder 不是新建——它只是把 ContextComposer 从 Pipeline 的私有实现提升为 Product 层的可见能力。
让用户能看到自己的 Context 长什么样，比让 AI 看到更重要。

### 为什么 Timeline + Relationship 在 Profile 之后

**Profile 是基础层。** Timeline 需要 Profile 的 created_at/updated_at 才能展示变化。
Relationship 已经作为 Projection 存在，它的数据已经有——Product 层只需要把它做成界面。

### 核心理念（不变）

```
Engine 是发动机。Product 是汽车。
用户不会买发动机——用户买的是汽车。
```

用户看到的应该是：
```
Alice — 关系档案
───────────────
最近聊天：2小时前，关于考试
共同兴趣：Python、CAD
最近情绪：焦虑（准备考试）
提醒：Alice 生日还有 5 天
关系阶段：朋友（正在升温）
```

不是：
```
Event Log: 1423 events
FactProjection: 18 active facts
PipelineResponse: metadata.event_count=1423
```

---

## Product 2.0 — 未来 (由用户需求驱动)

**不做预先设计。等真实用户反馈。**

可能的方向：
- MCP 接口收敛 (12 Tools → 2 Tools)
- Web UI (当前已有 chat.html 基础)
- Multi-user 隔离
- Claude / GPT / Gemini 全接入
- 记忆导出 / 导入

---

## Platform 1.0 — 远期 (有规模后)

**等日活超过开发者本人再说。**

- SQLite Storage (不改业务代码)
- Incremental Replay (snapshot + read_since)
- Raft / HA
- Redis / Kafka
- Cloud deployment
- OpenTelemetry / Grafana
- Plugin system
- SDK

---

## 版本哲学

```
Engine 1.0 — 冻结，永远稳定
Product 1.0 — 让用户感受记忆的价值
Product 2.0 — 由用户需求驱动
Platform 1.0 — 有规模再做

不要在没有用户的时候设计高可用。
不要在功能不完整的时候设计分布式。
不要在没有反馈的时候设计下一代架构。
```

---

*Engine 1.0 tag: v1.0.0-engine*
*Product 1.0: 进行中*
