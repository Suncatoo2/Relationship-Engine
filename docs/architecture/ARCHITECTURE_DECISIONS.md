# Architecture Decision Records (ADR)

> 记录每一个架构决策的原因。代码会变，但决策的理由不会过期。
> 以后接手这个项目的人，看这份文档就能理解当初为什么这么做。

---

## ADR-001: Everything is Event

**日期：** 2026-06-25
**状态：** Accepted

### 决策

所有系统输入（用户消息、事实提取、情绪记录、关系变化）都以 Event 形式存储在 append-only JSONL 文件中。

### 原因

1. Event 不可修改 = 天然审计日志
2. 所有 Projection 从 Event 重新计算 = 数据天然一致
3. 新增能力 = 新增 Event Type + 新增 Projection，不改核心架构
4. 升级算法 = 重新 replay Event，不用迁移数据库

### 备选方案

- **关系型数据库**：查询强，但 event 的不可变性需要应用层保证
- **内存状态管理**：快，但重启后数据丢失

### 后果

- 数据量足够大时（百万级），全量 Replay 性能受影响 → ADR-004（Snapshot）
- Projection 必须 Stateless → ADR-002

---

## ADR-002: Projection 必须 Stateless + Immutable

**日期：** 2026-06-27
**状态：** Accepted

### 决策

所有 Projection 是纯函数：`project(events) → Profile (frozen dataclass)`，无成员变量，无内部状态。

### 原因

1. 纯函数可独立测试：`assert proj.project(events) == expected`
2. 可缓存：同样的 events → 同样的 result
3. 可并发：无共享状态，多线程安全
4. 可重放：Event Sourcing 的标准模式

### 备选方案

- **有状态 Projection**：通过 `self.state` 维护上次计算的状态。更快，但难测试、难并发。
- **缓存 Projection**：在 Projection 内部缓存。职责混淆——缓存应该是外部策略。

### 后果

- 全量 replay 每次都要扫描全部 events → ADR-004（Snapshot + Incremental）
- Frozen dataclass 限制了内部的可变性 → 这不是缺陷，是设计保证

---

## ADR-003: Engine never competes with LLM for thinking

**日期：** 2026-06-27
**状态：** Accepted

### 决策

Engine 是确定性的管道。LLM 负责所有需要"理解"和"判断"的工作。Engine 不做推理，不做猜测，不做情绪判断。

### 原因

1. LLM 擅长不确定性（理解、推断、判断），Engine 擅长确定性（存储、计算、验证）
2. 如果 Engine 做推理，换模型时需要改 Engine
3. 职责清晰 = 测试清晰
4. 确定性管道可以做到 100% 可重现

### 备选方案

- **Engine 内嵌规则判断**：更自主，但换模型时规则失效
- **混合模式**：部分推理放 Engine、部分放 LLM → 边界模糊，难维护

### 后果

- 所有"理解"依赖 LLM，LLM 输出错误 → Engine 会忠实地存储错误数据
- 解决：Confidence 字段 + times_confirmed + provenance 追溯

---

## ADR-004: Storage 必须抽象

**日期：** 2026-06-27
**状态：** Accepted

### 决策

业务逻辑永远不直接读写文件，只能通过 `Storage` 抽象接口。当前实现是 JSONL，未来可切换到 SQLite、图数据库。

### 原因

1. 今天的数据量（< 10K events）JSONL 完全够用
2. 未来数据量增长（> 100K events），需要索引和复杂查询
3. 业务代码不应该知道底层存储细节

### 备选方案

- **直接用 JSONL 不抽象**：简单，但未来切换存储要大改
- **直接用 SQLite**：功能强，但增加了依赖，调试不如 JSONL 方便

### 后果

- Storage 接口需要设计足够通用，同时不能过度抽象
- 切换存储时，32 个测试应全部照旧通过

---

## ADR-005: 高层只有一个入口 — publish_interaction()

**日期：** 2026-06-27
**状态：** Accepted

### 决策

Engine 对外只有一个高层入口：`publish_interaction(interaction)`。LLM 决定"这次交互产生了什么"，一次性交给 Engine。

### 原因

1. 当前 MCP Tools 有 7 Write + 5 Read = 12 个独立接口，增加复杂度
2. 高层入口让 LLM 做结构化判断后一次提交，Engine 内部处理分发
3. 新增 Projection 不需要新增 Tool

### 备选方案

- **保持当前 MCP Tools 碎片化**：灵活，但每加一个能力就要加一个 Tool
- **RESTful CRUD**：通用性高，但语义太底层

### 后果

- `publish_interaction()` 的 schema 需要持续演进
- MCP Tools 保留为低层接口（给非 LLM 的外部系统调用）

---

## ADR-006: Event Schema 演进 + Pipeline 铁律

**日期：** 2026-06-28
**状态：** Accepted

### 决策 A：Event 字段从 v1 起预留演进空间

Event 字段固化如下：

| 字段 | 生成者 | 说明 |
|------|--------|------|
| `event_id` | Storage（append 时） | 全局唯一 ID，业务代码不可伪造 |
| `version` | 业务代码 | 固定为 1，未来 Schema 演进时递增 |
| `occurred_at` | 业务代码 | 业务发生时间（用户说话的时刻） |
| `recorded_at` | Storage（append 时） | 系统真正写入的时刻 |
| `type` | 业务代码 | 事件类型 |
| `person` | 业务代码 | 涉及人物 |
| `data` | 业务代码 | 事件载荷 |
| `source` | 业务代码 | 来源标识 |

区分 `occurred_at` 和 `recorded_at` 的原因：
- 用户 3 天前说了一句话，今天才录入系统 — 没有 `occurred_at`，时间线就错了
- 未来可能支持离线消息导入、外部数据迁移
- 审计/调试/Replay 依赖 `recorded_at` 定位写入顺序

### 决策 B：Pipeline 铁律（ADR-006 第二部分）

**只有 InteractionPipeline 可以访问 Event Store。**

允许的调用链：
```
Pipeline → Storage.append(event)     # 唯一写入
Pipeline → Storage.read() → events  # 唯一读取
```

禁止的调用链：
```
Projection → Storage.read()    ❌
Projection → EventLog.iter()   ❌
MemoryEngine → EventLog        ❌
MCP Server → EventLog          ❌
```

原因：
1. Projection 只消费 Event，不主动扫描历史 — 否则多个 Projection 各自读 Event Store，系统耦合
2. 统一入口 = 统一缓存策略（Snapshot）、统一性能监控
3. 将来换 Storage，只需改 Pipeline 一处

### 备选方案

- **每个 Projection 自己读 Event Store**：灵活，但 8 个 Projection × 各自查询 = N × M 种耦合

### 后果

- 所有 Event 必须经过 Pipeline 写入
- `MemoryEngine` 的 `recall()` 职责迁移到 `Pipeline.recall()`
- 中间件/日志/验证 全部在 Pipeline 层实现
- **Pipeline 自身不超过 200 行** — 只做协调，不负责实现。实现代码下沉到 Dispatcher / Projection / Validator / ContextComposer 中

---

## ADR-007: Engine Detects, LLM Explains

**日期：** 2026-06-28
**状态：** Accepted

### 决策

Engine 负责**发现（Detect）**，LLM 负责**解释（Explain）**。

Engine 发现的是确定性事实：
- 30 天未联系
- 情绪连续下降 5 天
- 生日还有 2 天
- Relationship Lifecycle 进入冷却阶段
- 目标 3 个月没有提及

LLM 解释的是人的表达：
- "最近是不是有点累？"
- "要不要联系一下 Bob？"
- "Alice 快生日了，你准备送什么？"

### 原因

1. 发现是确定性的——`days_since_last_contact > 30` 是 100% 可重现的
2. 解释是不确定性的——"要不要联系"需要理解上下文和语气
3. Engine 做发现，100% 可测试；LLM 做解释，无法单元测试
4. 换 LLM 时，发现逻辑不变；升级 Engine 时，解释风格不变

### 备选方案

- **Engine 做解释**：不可测试，换模型时风格丢失
- **LLM 做发现**：浪费 token，不确定性引入确定性任务

### 后果

- `suggestions` 字段由 Engine 生成（确定性规则），不由 LLM 生成
- `memory_summary` 由 Engine 生成（结构化摘要），Prompt 风格由 Adapter 生成
- Engine 的每个 Detect 都必须是可断言的：`assert days > 30`
- LLM 的每个 Explain 都是自由文本，不可断言

---

## ADR-008: Interaction Philosophy（交互哲学）

**日期：** 2026-06-28
**状态：** Accepted

### 决策

建立 Interaction Philosophy，定义 Relationship Engine 与用户交互的顶层原则。
这些原则不依赖任何具体 LLM，是产品的"灵魂"。

### 三层模型

```
Engine Detects → PromptAdapter Constrains → LLM Generates
Engine 不推理 → PromptAdapter 不思考 → LLM 自由生成
```

### 核心原则

1. **Memory should be demonstrated, never announced.**
   记忆应该被展示，而不是被宣告。AI 不需要说"我记得你"，而是在对话中自然地接上历史上下文。

2. **Memory should feel acknowledged, not announced.**
   记忆应该被自然地确认，而不是被正式地宣告。"好，我会记着"，不是"已写入数据库"。

3. **Show, don't tell.**
   用行动证明记忆，不用嘴念叨。用户一年后回来说"我和小雨怎么样了"，AI 直接用事实回答，不煽情。

4. **Suggestions are intents, not commands.**
   建议是意图，不是指令。Engine 输出 `time_gap = 30d`，PromptAdapter 输出行为约束，LLM 决定怎么说。

5. **Engine outputs facts, not derivations.**
   Engine 只输出客观事实（`time_gap = 30d`），不输出推导（不用 `silence_alert = true`）。

6. **PromptAdapter outputs constraints, not prose.**
   PromptAdapter 输出可验证的行为规则（"Do not describe yourself as remembering"），不输出文学指导（不用 "without judgment"）。

### PromptAdapter 行为约束示例

```
当 time_gap >= 7d:
  - Allow one sentence acknowledging the time gap.
  - Do not ask where the user has been.
  - Do not express emotion about the absence.
  - Do not announce that memory is preserved.
  - Keep response brief. Let the user lead.

当 time_gap >= 30d:
  - Same as 7d, plus:
  - Do not introduce historical topics proactively.
  - Let factual continuity imply persistent memory.

当 time_gap >= 180d:
  - Same as 30d, plus:
  - First response should be maximally brief.
  - Give full initiative to the user.
```

### 后果

- Interaction Philosophy 独立于任何 LLM，是产品的"灵魂"
- 换 GPT/Claude/DeepSeek 时，这些原则不变
- PromptAdapter 只维护 signal → constraint 映射表，不维护文案

---

## ADR-009: Memory Retrieval Policy

**日期：** 2026-06-28
**状态：** Accepted

### 决策

明确 Memory Retrieval（记忆检索）的触发条件、排序规则、生命周期和 Projection 边界。

### Retrieval Trigger

当 Pipeline.recall() 被调用时触发历史召回。每次 recall 都从 Event Log 全量或增量读取，由 Projection 重新计算。

### Retrieval Ranking

```
Score = Semantic Relevance + Temporal Distance + Relationship Weight + Importance
```

- Semantic Relevance: 按关键词/embedding 匹配（Phase 3+ 实现）
- Temporal Distance: 最近的事件权重更高
- Relationship Weight: 亲密人物的记忆优先
- Importance: LLM 标记的重要性权重

### Working Memory Lifecycle

ContextObject 每轮根据当前 recall 重建。不是持久化缓存。

```
查询 "小雨考试" → Working Memory: 小雨相关
查询 "外卖"     → Working Memory: 外卖相关（小雨退出）
查询 "天气"     → Working Memory: 天气相关（外卖退出）
```

### Projection Boundary

Engine 只做 Detect，不做 Infer。

```
允许（Deterministic Detection）:
  time_gap, days_since_last_contact, chemistry_decay

禁止（Semantic Inference）:
  last_topic, emotion_label, user_intent, mood_cause
```

### 后果

- Working Memory 不跨轮次缓存
- ContextObject 每轮重建（project() 纯函数天然支持）
- Retrieval Ranking 持续演进，但不影响 Pipeline.recall() 接口
