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
