# Architecture Checkpoint — v0.3.95

**日期：** 2026-06-27
**版本：** v0.3-stable + FactProjection
**TAG：** v0.3-stable (本地)
**状态：** ✅ Architecture Review 完成, Step 4 待开始

---

## 架构图（当前）

```
Event Log（append-only JSONL）
    │
    ├──→ FactProjection ──→ FactState（frozen）
    ├──→ PersonProjection ──→ PersonProfile
    ├──→ RelationshipProjection ──→ RelationshipProfile
    ├──→ TimeContextProjection ──→ TimeContextProfile
    ├──→ EmotionProjection ──→ EmotionProfile
    ├──→ GrowthProjection ──→ GrowthProfile
    ├──→ ReminderProjection ──→ ReminderProfile
    ├──→ ConversationProjection ──→ ConversationProfile
    │
    ▼
Memory Engine（编排层）
    ├── FactProjection → active facts → Memory Selector → 筛选
    ├── Context Composer → ContextSnapshot
    ├── Prompt Builder → Prompt 文本
    ├── 断言验证：同 category 无重复
    │
    ▼
Provider Layer → LLM
```

## Projection 目录结构

```
src/projections/
├── base.py              # Projection 基类 (Stateless)
├── fact_state.py        # ← Step 3.95: 事实状态投影 (纯函数)
├── person.py            # 人物画像
├── relationship.py      # 关系状态 + 衰减
├── time_context.py      # 时间感知
├── emotion.py           # 情绪摘要
├── growth.py            # 成长时间线
├── reminder.py          # 智能提醒
├── conversation.py      # 对话分析
├── context.py           # Context Composer
└── prompt_builder.py    # Prompt Builder
```

## FactProjection 设计原则

- **Stateless** — 无成员变量，纯函数：`project(events) → FactState`
- **Immutable** — FactState + FactItem 都是 frozen dataclass
- **每个 category 有且仅有一个 active fact**
- **渐进式重构** — `_resolve_conflicts` 作为断言保留（未来稳定后删除）
- **位置** — 和其他 Projection 并列，不是特殊模块

## 为什么 Incremental Projection 暂缓

```
现在：几千条 Event，全量 Replay < 1s
未来：百万条 Event → 实现 Snapshot + since_event_id
接口已预留：project(events, since=None) → FactState
```
**先正确，再快速。**

## 测试

- 32/32 Memory Test Suite passed
- FactProjection: 覆盖 + 去重 + frozen 验证 ✅

## 下一步：Step 4 — Memory 分层

将事实按语义分层：
- Facts（纯事实）
- Preferences（偏好，动态权重）
- Personality（人格画像）
- Emotion（情绪，已有基础）

每层基于 FactProjection 的 category 字段构建。

## 回滚策略

```
回滚到 Step 3.95：
  git checkout v0.3-stable

回滚到 Step 3.8 前：
  git checkout v0.3-memory-foundation
```

---

*最后一次更新：2026-06-27*
