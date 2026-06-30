# Relationship OS — Roadmap

> Vision 是梦想，Roadmap 是路线。打开这一个文件就知道项目在哪。
> 最后更新：2026-06-30

---

## 版本阶段



### v1.0.0-baseline — 稳定底座 ✅ (2026-06-30)

Product 1.0 的第一个稳定基线版本。包含：

| 能力 | 状态 |
|------|------|
| ProfileProjection (第 9 号 Projection) | ✅ |
| Infrastructure hardening (PipelineResponse, WAL, capability guard) | ✅ |
| Memory Retrieval & Ranking (query-aware recall + token budgeting) | ✅ |
| Cross-Projection Reasoning Engine (5 条推理规则) | ✅ |
| ConsumerFacade unification (MCP/Web 统一入口) | ✅ |
| Architecture enforcement Phase 1 (compliance tests) | ✅ |
| 507 tests (0.88s) | ✅ |

Remaining Product 1.0 work:

| Step | 名称 | 状态 |
|------|------|------|
| Step 4 | Closed Feedback Loop | 📋 Future |
| Step 5 | Self Evolution | ⏳ Design Only |

> v1.0.0-baseline 不是「产品完成」。
> 它是「稳定底座完成」——可以作为 Step 4 / Step 5 的可靠起点。
> 不包含 Closed Feedback Loop，不包含 Self Evolution。
> 但它包含了一个完整的 Engine：Event → 9 Projections → Reasoning → Ranking → ContextObject → LLM。

---

## Engine 1.0 — Frozen ✅

**目标：永远稳定。除非 Bug，不新增底层能力。**

### 交付物

| 类别 | 能力 | 状态 |
|------|------|------|
| Event Sourcing | Event Log (JSONL) + 9 Projections | ✅ |
| Pipeline | publish / recall / decompose | ✅ |
| PipelineResponse | context / metadata / diagnostics (ADR-010) | ✅ |
| Capability Guard | Token-based runtime enforcement (ADR-011) | ✅ |
| Crash Recovery | WAL + Atomic Write + Recovery Replay (ADR-012) | ✅ |
| Snapshot Integrity | Checksum + Schema Version + Rebuild | ✅ |
| Observability | dispatch_stats, timing, health, warnings | ✅ |
| Retrieval & Ranking | Query-aware recall + token budgeting (ADR-008) | ✅ |
| Architecture | 15 ADRs + contract tests | ✅ |
| Test Coverage | 447 tests (0.73s) | ✅ |

### 冻结范围

以下内容 **不再修改**：
- Event schema
- Pipeline 接口 (publish, recall, snapshot, rebuild)
- Storage 接口 (append, read_all, read_since, count, health)
- Projection 接口 (apply, snapshot, project)
- PipelineResponse 字段 (context, metadata, diagnostics)

以下内容 **可以修改**：
- 新增 Projection (不影响已有 9 个)
- 新增 EventType (不修改已有字段)
- 新增 RetrievalStrategy (不修改 ranker 接口)
- Performance tuning (不改变接口语义)
- Bug fixes

---

## Product 1.0 — Pipeline

**目标：从「引擎」到「产品」——让用户感受到记忆的价值。**

### Step 1: ProfileProjection ✅
第 9 号 Projection。长期关系档案。21 tests。

### Step 2: Memory Retrieval & Ranking ✅
查询感知记忆召回。3种策略 + token budgeting。47 tests。

### Step 3: Cross-Projection Reasoning 📋
不是 Compose——是 Reason。跨投影关联推理。确定性规则。

### Step 4: Closed Feedback Loop 📋
publish → recall → LLM → publish 闭环。Session Orchestrator。

### Step 5: Self Evolution ⏳
无用户数据不写代码。等待 Step 4 的反馈。

---

## Product 2.0 — 用户驱动

**不做预先设计。等真实用户反馈。**

---

## 版本哲学



---

*Engine 1.0 frozen. Product 1.0 in progress.*
*每完成一个 Step，回来更新这个文件。*
