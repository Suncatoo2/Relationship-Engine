# ADR-011: Architecture Evolution Policy

**日期：** 2026-06-28
**状态：** Accepted (Architecture: v0.8)

---

## 决策

定义 Relationship OS 的架构演进规则。不依赖人的记忆来触发重构——由系统规则和信号驱动。

---

## 1. Deferred Specialization（延迟专门化）

当前不拆分某个 Projection，不是因为它永远简单，而是刻意推迟专门化，等待真实需求成熟。

```
现在: category="goal" → FactProjection 内部处理
未来: Goal 数据密度达到阈值 → 拆分为独立 GoalProjection
```

这不是技术债，是**有意识的延迟决策**。

---

## 2. Architecture Seam（架构接缝）

为未来拆分预留稳定的演进接缝，今天只是简单函数。

```python
# 今天: 一个 helper
def parse_goal_from_fact(fact_item) -> GoalItem:
    return GoalItem(title=fact_item.content, category="goal", ...)

# 未来: 替换整个入口，Pipeline 不感知
class GoalProjection(Projection):
    def apply(self, event): ...
    def project(self, events): ...
```

**原则：留下可替换的接缝，而不是未来不得不重写的代码。**

---

## 3. Architecture Evolution Triggers（架构演进触发器）

重构不是凭感觉——由量化信号驱动。

```
Trigger 条件                    →  动作

Goal 数据密度 > 50 events          →  ARCHITECTURE WARNING
Schema 字段数 > 当前定义 + 3       →  Projection Split Review
特定 category 事件增长率 > 30%/月 →  独立 Projection 评估
用户反馈 ≥ 3 次同类诉求           →  需求验证通过
Projection.project() > 100ms       →  性能优化触发
```

这些触发条件可以存在于文档中，未来可以自动化到 CI/Metrics。

---

## 4. Pipeline Purity（Pipeline 纯净原则）

**Pipeline 不因任何 category 的特殊处理而增加 if/else。**

```
Pipeline          → 负责流程（publish / recall），不改
Projection        → 负责结构（apply / project / snapshot）
Parser / Helper   → 负责解析（纯函数，零副作用）
```

如果某个 category 的复杂度持续增长：

```
第一阶段: Parser helper（纯函数，Pipeline 不感知）
第二阶段: 独立 Projection（注册到 Dispatcher）
第三阶段: 独立 Engine（如果语义复杂度超标）
```

每一层的职责保持稳定。Pipeline 永远是 37 行。

---

## 5. Projection Split Decision Tree

```
某个 category 是否需要拆分为独立 Projection？

  1. 事件数量 > 阈值（如 50+ events）？
     ↓ YES → 2
     ↓ NO  → KEEP（延迟专门化）

  2. 是否有 category 特有的字段（如 target_date, deadline）？
     ↓ YES → 3
     ↓ NO  → KEEP（通用字段足够）

  3. 是否有独立的业务逻辑（如 progress tracking）？
     ↓ YES → SPLIT（独立 Projection）
     ↓ NO  → MONITOR（等待需求成熟）
```

---

## 原则总结

```
1. Deferred Specialization      — 刻意推迟，不是技术债
2. Architecture Seam            — 预留可替换的接缝
3. Quantified Triggers          — 系统信号驱动，不是人的记忆
4. Pipeline Purity              — 不加 if/else，不因 category 变复杂
5. Progressive Specialization   — Parser → Projection → Engine，渐进演化
```

---

## 后果

- GoalProjection 现在不拆分，但 `_goals()` 方法已存在于 ContextComposer 中作为接缝
- 未来任何 category 的增长都遵循 Split Decision Tree
- Pipeline 永远不加业务分支（if/else on category）
- 当触发条件满足时，重构不是"返工"，是"按计划执行"

---

## 6. Business Policy Isolation（业务策略隔离）

**日期：** 2026-06-28

### 决策

产品策略（如时间阈值 30d / 60d）与核心算法分离。

```
BoundaryPolicy
  ↓ (策略对象，可替换)
_compute_boundary()  ← 算法，不持有 magic numbers
```

### 规则

- 时间阈值、置信度参数、重要性级别属于 Product Policy
- Policy Object 集中管理所有阈值
- 核心算法只调用 Policy，不直接使用 magic numbers
- 未来 Friend / Partner / Family 不同策略通过 Policy 扩展
- 策略调整不修改核心算法

### 依赖方向

```
Boundary → Confidence → Health
（禁止逆向依赖）
```

任何形成循环依赖的修改必须重新评审。

### 当前 Acceptance

- `src/boundary_policy.py` — BoundaryPolicy（30d / 60d 阈值 + confidence 参数）
- `_compute_boundary()` 调用 BoundaryPolicy，不持有 magic numbers
- White-box tests 验证阈值可修改后算法行为正确
