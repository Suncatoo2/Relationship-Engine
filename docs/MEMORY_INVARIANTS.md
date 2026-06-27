# Memory Invariants — 记忆不变量

> 无论代码怎么变，这些规则永远不变。
> 如果某个 Bug 出现了，先拿这个文档检查。

---

## 规则清单

### 1. 唯一活跃值
同一 Preference（如同一个 category+value）永远只能有一个 ACTIVE 的值。

### 2. 废弃不进 Prompt
DEPRECATED 和 ARCHIVED 状态的 Memory 永远不进入 Prompt。

### 3. 归档不参与检索
CONFLICT 状态的 Memory 不进入 Prompt，但保留以等待确认。

### 4. 归档不检索
ARCHIVED 状态的 Memory 永远不参与任何检索。

### 5. Context 只读活跃记忆
Context Composer 只能读取 ACTIVE 或 CONFIRMED 状态的 Memory。

### 6. Metadata 必须完整
任何 Memory 都必须拥有完整的 metadata（confidence, source, created_at, status）。

### 7. 覆盖必须保留历史
任何对 Memory 的修改都不能删除旧版本。旧版本标记为 DEPRECATED，保留完整数据。

### 8. 删除是归档，不是真删除
不存在真正的删除操作。DELETE 等价于 ARCHIVE。Event Log 永远不变。

### 9. Memory ID 永久不变
每条 Memory 从创建到归档，ID 永远不变。历史查询靠 ID 追踪。

### 10. Event 不可修改，Memory 可以更新
Event Log 中的原始事件不可修改。Memory 的状态可以从 ACTIVE 变为 DEPRECATED，但 Event 保留原样。

---

## 记忆状态机（完整版）

```
用户说话
    │
    ▼
EXTRACTED  ──→ 从聊天中提取（低可信）
    │
    ▼
VALIDATED  ──→ 通过基本验证（中等可信）
    │
    ▼
CONFLICT   ──→ 发现冲突，等待确认 ← 新增
    │
    ├── 用户确认覆盖 → 旧值 DEPRECATED, 新值 ACTIVE
    ├── 用户否定新值 → 新值 DISCARDED, 旧值保持 ACTIVE
    └── 用户忽略    → 新值保持 CONFLICT, 定期重问
    │
    ▼
ACTIVE     ──→ 正常使用中
    │
    ├── 多次确认 → CONFIRMED
    ├── 很久没提 → STALE
    └── 被新值覆盖 → DEPRECATED
              │
              ▼
          ARCHIVED

CONFIRMED  ──→ 多次确认，高可信
STALE      ──→ 需要重新确认
DEPRECATED ──→ 被覆盖的历史值
ARCHIVED   ──→ 长期归档
```

## 为什么需要 CONFLICT 状态？

```
用户说："我喜欢蓝色"     →  ACTIVE: favorite_color=blue
后来："其实现在更喜欢绿色" →  CONFLICT: favorite_color=?
```

此时系统不应该直接覆盖，因为：
1. 用户说的是"现在更喜欢"，不是"不喜欢蓝色"
2. AI 从聊天中推断的，不是用户明确声明

CONFLICT 状态的 Memory：
- 不进入 Prompt（避免混淆）
- 保留数据等待确认
- 用户下次提到时，AI 可以主动问："你之前喜欢蓝色，现在还喜欢吗？"

---

*版本：v0.3-memory-foundation*
*作者：Suncatoo2*
