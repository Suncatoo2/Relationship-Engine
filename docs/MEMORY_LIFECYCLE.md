# Memory 生命周期

Relationship Engine 中每一条记忆的完整生命周期。

```
用户说了一句话
      │
      ▼
┌─────────────────────┐
│ Memory Extractor    │  自动识别事实声明
│ _auto_extract_facts │  "我喜欢蓝色" → fact event
│ Pattern + Regex     │  "我是口腔专业" → fact event
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Event Log           │  append-only JSONL
│ (唯一数据源)         │  所有数据以 Event 形式存储
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Memory Engine       │  编排层
│ recall()            │  协调 Selector → Reasoner → Composer
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Memory Selector     │  "找"
│ select()            │  关键词匹配 + importance 加权
│                     │  选出 top N 条相关记忆
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Memory Reasoner     │  "想"  (v0.4，接口已预留)
│ reason()            │  分析记忆之间的关联
│                     │  推断用户的情绪、偏好、目标
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Context Composer    │  "写"
│ compose()           │  7 个 Projection 并行计算
│                     │  生成 ContextSnapshot
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Prompt Builder      │  格式转换
│ build()             │  ContextSnapshot → LLM Prompt
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Provider Layer      │  模型无关接入
│ stream_chat()       │  DeepSeek / Claude / GPT / Gemini
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Response            │  用户看到的 AI 回复
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Prompt Log          │  完整链路保存
│ save_prompt_log()   │  user_message + context + reply + provider_debug
└─────────────────────┘
```

## 记忆状态机

```
                    ┌──────────────┐
                    │     NEW      │  刚创建，尚未确认
                    └──────┬───────┘
                           │ 用户第一次提到
                           ▼
                    ┌──────────────┐
              ┌────→│    ACTIVE    │  正常使用中
              │     └──┬────┬──┬──┘
              │        │    │  │
              │ 多次确认│    │  │ 很久没提
              │        │    │  │
              │        ▼    │  ▼
              │ ┌─────────┐ │ ┌──────────┐
              │ │CONFIRMED│ │ │  STALE   │  需要再次确认
              │ └────┬────┘ │ └────┬─────┘
              │      │      │      │
              │      │      │ 用户否定│ 仍然不提
              │      │      │      │
              │      │      ▼      ▼
              │      │  ┌──────────────┐
              │      │  │  DEPRECATED  │  被新值覆盖
              │      │  └──────┬───────┘
              │      │         │
              │      │         ▼
              │      │  ┌──────────────┐
              │      │  │   ARCHIVED   │  归档保留
              │      │  └──────────────┘
              │      │
              └──────┴──────── 用户重新确认，状态回到 ACTIVE
```

## 记忆状态定义

| 状态 | 含义 | Selector 行为 | 触发条件 |
|------|------|-------------|---------|
| NEW | 刚创建，首次出现 | 正常选择 | 用户第一次声明 |
| ACTIVE | 正常使用中 | 正常选择 | 最近确认过的 |
| CONFIRMED | 多次确认，高可信 | 优先选择 | times_confirmed >= 2 |
| STALE | 很久没提，可能变了 | 降低权重 | last_confirmed > 90天 |
| DEPRECATED | 被新值覆盖 | 不选择（除非查历史） | 用户说"现在更喜欢X" |
| ARCHIVED | 已归档，仅供追溯 | 不选择 | deprecated > 180天 |
| DELETED | （几乎不用） | 不选择 | Event Log 不删除 |

## 冲突解决流程

```
新事实到达
      │
      ▼
检查是否有同类旧事实（同 category）
      │
      ├── 无冲突 → 状态 = ACTIVE
      │
      └── 有冲突
              │
              ├── 用户明确否定旧值 → 旧值 = DEPRECATED, 新值 = ACTIVE
              │
              ├── 模糊表达（"最近更喜欢..."）→ 旧值 = STALE, 新值 = ACTIVE
              │
              └── 语义相同（"喜欢蓝" = "喜欢蓝色"）→ 合并, times_confirmed++

```json
{
  "type": "preference",
  "value": "蓝色",
  "source": "user_direct",
  "confidence": 0.98,
  "importance": 8,
  "importance_reason": "个人偏好",
  "created_at": "2026-06-27",
  "last_confirmed": "2026-06-27",
  "times_confirmed": 3,
  "status": "active"
}
```

## 记忆状态机

```
active     → 当前有效的记忆
deprecated → 被更新的记忆覆盖（保留历史）
dormant    → 很久没确认，可能已失效
deleted    → (几乎不用，Event Log 不删除)
```

## 未来模块接口（Open for Extension）

```
MemoryReasoner.run(selected_facts, query) → inferences
EmotionEngine.run(events) → emotion_state
RelationshipEngine.run(events) → relationship_state
PersonaEngine.run(facts, inferences) → persona_profile
```

每个引擎现在返回 `{}`，但不影响 Selector 和 Composer。
以后填充实现时，不需要改任何现有模块。

## 测试矩阵

```
tests/
├── memory/
│   ├── test_preference.py      喜好记忆
│   ├── test_overwrite.py       覆盖旧记忆
│   ├── test_multi_user.py      多用户隔离
│   ├── test_conflict.py        冲突解决
│   ├── test_interference.py    干扰测试
│   ├── test_long_context.py    长上下文检索
│   └── test_inference.py       推理测试
```

---

*每增加一个模块，更新这张图。*
