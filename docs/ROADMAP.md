# Relationship OS — Roadmap

> Vision 是梦想，Roadmap 是路线。打开这一个文件就知道项目在哪。
> 最后更新：2026-06-28

---

## 版本语义

```
Development Milestones（开发里程碑）:
  记录真实开发过程，不等于正式版本。
  v0.3-stable, v0.4-pipeline, v0.5-context-filled

Architecture Releases（架构阶段）:
  每个版本锁定一层架构能力，不可回退。
  v0.4.0 → v0.5.0 → v0.6.0 → v1.0.0
```

---

## v0.4.0 — Infrastructure（基础设施）📋

**目标：从此以后，没有任何数据能绕过 Pipeline。**

### 交付物

| # | 交付物 | 状态 |
|---|--------|------|
| 1 | Pipeline（publish/recall/snapshot/rebuild） | ✅ |
| 2 | Dispatcher（registry 模式，event_type 路由） | ✅ |
| 3 | BaseStorage（ABC: append/read_all/count） | ✅ |
| 4 | JSONLStorage（含 read_since 增量读取） | ⚠️ read_since 待加 |
| 5 | Event Schema（version/occurred_at/recorded_at） | ✅ |
| 6 | ContextObject（冻结结构，最后一次结构性变更） | ⚠️ 加 GoalsBlock |
| 7 | Snapshot 基础接口（Projection.snapshot()） | ✅ |
| 8 | web_server 接入 Pipeline（读写全部） | ✅ |
| 9 | mcp_server 接入 Pipeline（读写统一） | ❌ 待做 |
| 10 | 测试体系升级（4 类新测试） | ❌ 待做 |

### 验收标准

```
Write 路径:
  LLM → publish_interaction() → Pipeline → Storage → Dispatcher → Projection

Read 路径:
  LLM → get_context(person) → Pipeline.recall() → ContextObject JSON

红线:
  - LLM 不再感知 Storage 和 EventLog 的存在
  - 旧接口（get_person/get_emotion/get_tasks）deprecated 或 thin wrapper
  - 没有任何业务代码直接访问 EventLog
```

### MCP Interface 收敛

```
Write Tools → publish_interaction()（统一入口）
  替代: add_person, remember, add_chat, add_emotion,
        update_relation, add_milestone, add_growth

Read Tools → get_context(person_name)（统一出口）
  替代: get_person, get_events, get_reminders, search
  输出: ContextObject JSON（标准结构，不可变）

兼容层:
  旧 Read Tool 可保留为 thin wrapper，内部调用 pipeline.recall()
  但不再直接访问 Storage 或 EventLog
```

---

## v0.5.0 — Memory Core（记忆核心）✅

**目标：Memory Engine 能稳定产出完整的 Context，不再修改底层数据结构。**

- ✅ memory_summary 填充（Reasoner → MemoryBlock）
- ✅ Golden ContextObject（固定 JSON 作为标准输出）
- ✅ GoalsProjection 验证（category="goal" 通过）
- ✅ Projection Framework 完善（info/project_all(person)）
- ✅ Context Regression Test（12 个测试）
- ✅ alice_demo.py + MEMORY_FLOW.md

---

## v0.6.0 — Output Layer（输出层）📋

**目标：从"被动记忆"走向"主动理解"。Engine 负责发现，LLM 负责解释。**

### PromptAdapter（输出编译层）

```
ContextObject
    ↓
PromptAdapter（不是语气模块，是 Output Compiler）
    ├── 根据关系深度调整语气（陌生人→朋友→亲密）
    ├── 注入 Suggestions（Engine 生成，不是 LLM）
    ├── 组织 Context 结构（哪些信息优先）
    └── 适配 LLM 格式（Claude XML / GPT Markdown / DeepSeek 纯文本）
    ↓
最终 Prompt
    ↓
不同 LLM
```

### Time-Aware Recall（时间感知召回）

**核心洞察：即使什么都没有发生，时间本身也会改变人与人的关系。**

```
Pipeline.recall() 读取当前系统时间
    ↓
TimeProjection 重新计算:
  - days_since_last_contact（实时更新）
  - 生日倒计时（自动变化）
  - silence_duration（持续增长）
  - decay_chemistry（实时衰减）
    ↓
RelationshipProjection 重新计算:
  - Relationship Lifecycle（季节检测）
  - 关系阶段自动变化
    ↓
ContextObject 因时间变化而自动更新
```

**不需要新 Event。Storage 不变。EventLog 不变。**
**ContextObject 会因为时间流逝而自然演化。**

### Emotion Momentum（情绪动量）

基于时间的指数衰减，不是滑动平均：

```
Momentum = Previous × e^(-λΔt) + Current

Δt = 距离上一条 Interaction 的真实时间（不是消息数量）

昨天很开心，今天突然难过 → 动量大（Δt 小）
两个月没聊天，今天突然难过 → 动量小（Δt 大）
```

### Proactive Suggestions（主动建议）

Engine 的确定性规则检测，不是 LLM 推理（ADR-007）：

```
条件 → 建议（Engine 生成，可断言）
─────────────────────────────────────
30天没联系 Bob         → "Bob 30 天没联系了"
Alice 生日还有 5 天     → "Alice 生日还有 5 天"
情绪连续 3 天下降       → "情绪连续下降 3 天"
目标 3 个月没提         → "考研目标 3 个月没有更新"
关系从暧昧变冷淡        → "关系阶段从暧昧变为冷淡"
```

LLM 负责把这些 Detect 转化为人的表达（ADR-007）。

### Relationship Lifecycle（关系生命周期）

```
春天: 初识 → 升温 → 频繁联系
夏天: 热恋/亲密 → 高频高质
秋天: 稳定 → 联系减少但质量不变
冬天: 冷淡 → 长期沉默 → 关系冻结

AI 应该识别:
  "你和 Alice 的关系正在进入秋天——联系频率下降，但每次聊天质量还很高。"
  "你和 Bob 已经 30 天没联系了，关系正在进入冬天。"
```

### Goal Projection 独立拆分

如果 category="goal" 验证通过，拆分为独立 Projection。

---

## v0.7.0 — Performance（性能层）📋

**目标：优化性能，不修改架构。**

- Snapshot 持久化（State @ Event_ID_X）
- Incremental Replay（read_since → snapshot → 只 replay 新事件）
- Cache
- Recovery

---

## v1.0.0 — Production（生产化）🎯

- 多 Agent 支持
- SQLite Storage（不改业务代码）
- 性能优化
- 并发验证
- 长期稳定性测试

---

## Future（远期规划）

当出现真实产品需求时再设计，不提前抽象。

- Security + Multi-Tenancy（JWT/OAuth/RBAC）— 当第一个真实用户需要登录时设计
- Multi-user sync
- Social Graph
- Community Edition
- Mobile App

---

## Milestones

| Tag | 类型 | 内容 | 状态 |
|-----|------|------|------|
| v0.3-stable | Dev Milestone | FactProjection + 32 tests | ✅ |
| v0.4-pipeline | Dev Milestone | Pipeline + Dispatcher + Storage | ✅ |
| v0.5-context-filled | Dev Milestone | ContextComposer + 5 Projections + MemoryReasoner | ✅ |
| v0.4.0-infrastructure | Arch Release | 基础设施闭环 | ✅ |
| v0.5.0-memory-core | Arch Release | 记忆核心稳定 | ✅ |
| v0.6.0-output-layer | Arch Release | 输出层 + 时间感知 + 主动理解 | ✅ |
| v0.7.0-performance | Arch Release | 性能优化 | 📋 |
| v1.0.0-production | Arch Release | 生产就绪 | 🎯 |

---

*每个 Architecture Release 完成后，打 GitHub Release。*
*每完成一个版本，回来更新这个文件。*
