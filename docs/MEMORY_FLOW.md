# Memory Flow — 数据流全景图

> 一句话看完整个系统：**用户说了一句话，AI 怎么记住、怎么理解、怎么回复。**

---

## 全景图

```
用户说了一句话
      │
      ▼
┌─────────────────────────────────────────────────┐
│  Interaction                                    │
│  { message, person, facts, emotion, relation }  │
│  LLM 结构化后的交互数据                           │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Pipeline.publish()          ← 唯一写入口        │
│                                                 │
│  1. decompose(interaction) → [Event]            │
│  2. Storage.append(event) × N                   │
│  3. Dispatcher.dispatch(event) × N              │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Event Log (Storage)                            │
│  append-only JSONL，不可修改                     │
│  每条 Event 有: event_id, occurred_at,          │
│                 recorded_at, version, type       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Dispatcher (registry 模式)                     │
│                                                 │
│  registry = {                                   │
│    "fact":     [FactProjection],                │
│    "emotion":  [EmotionProjection],             │
│    "relation": [RelationshipProjection],        │
│    "chat":     [TimeContextProjection, ...],    │
│    ...                                          │
│  }                                              │
│                                                 │
│  按 event.type 路由到对应的 Projection            │
│  Pipeline 不知道里面有几个 Projection             │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Projection Layer (6 个)                        │
│                                                 │
│  ┌──────────────┬──────────────────────────┐   │
│  │ Fact         │ Relationship             │   │
│  │ (事实去重)    │ (关系阶段+好感度+衰减)     │   │
│  ├──────────────┼──────────────────────────┤   │
│  │ Person       │ TimeContext              │   │
│  │ (人物画像)    │ (时间感知+沉默检测)       │   │
│  ├──────────────┼──────────────────────────┤   │
│  │ Emotion      │ Growth                   │   │
│  │ (情绪趋势)    │ (成长时间线)              │   │
│  └──────────────┴──────────────────────────┘   │
│                                                 │
│  每个 Projection:                               │
│    apply(event)    ← 增量更新（Pipeline 调用）    │
│    project(events) ← 批量计算（recall 时调用）    │
│    snapshot()      ← 状态快照（可选）            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Pipeline.recall(person)     ← 唯一读出口        │
│                                                 │
│  1. Storage.read_all()                          │
│  2. Dispatcher.project_all(events, person)      │
│  3. ContextComposer.compose(person, events,     │
│     profiles)                                   │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  ContextComposer                                │
│                                                 │
│  profiles → 6 个 Block:                         │
│  ┌─────────────────────────────────────────┐   │
│  │ IdentityBlock    name, tags, birthday   │   │
│  │ MemoryBlock      facts + memory_summary │   │
│  │ RelationshipBlock stage, chemistry      │   │
│  │ TimeBlock        last_chat, silence     │   │
│  │ EmotionBlock     trend, dominant        │   │
│  │ GoalsBlock       active goals           │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  内部调用 MemoryReasoner 生成 memory_summary     │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  ContextObject (冻结结构)                       │
│                                                 │
│  {                                              │
│    "identity": { "name": "Alice", ... },        │
│    "memory": {                                  │
│      "active_facts": [...],                     │
│      "memory_summary": "Alice喜欢蓝色..."        │
│    },                                           │
│    "relationship": {                            │
│      "stage": "朋友", "chemistry": 25           │
│    },                                           │
│    "emotion": { "dominant_emotion": "焦虑" },   │
│    "goals": { "active_goals": [...] },          │
│    "last_consumed_event_id": "abc-123"          │
│  }                                              │
│                                                 │
│  ⚠️ 结构已冻结，只加字段不改结构                  │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  PromptAdapter (v0.6 实现)                      │
│                                                 │
│  ContextObject → Claude XML Prompt              │
│  ContextObject → GPT Markdown Prompt            │
│  ContextObject → DeepSeek 纯文本 Prompt         │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  LLM → 回复                                     │
└─────────────────────────────────────────────────┘
```

---

## 关键约束

```
写入: 只有 Pipeline.publish() 可以写入 Event
读取: 只有 Pipeline.recall() 可以读取 Context
路由: 只有 Dispatcher 可以路由 Event 到 Projection
计算: Projection 只消费传入的 Event，不主动读 Storage
输出: ContextObject 是唯一输出，Prompt 是下游 Adapter 的事
```

---

## 文件索引

| 组件 | 文件 | 行数 |
|------|------|------|
| Pipeline | `src/interaction_pipeline.py` | ~37 (class) |
| Dispatcher | `src/dispatcher.py` | ~100 |
| Storage | `src/storage.py` | ~140 |
| ContextComposer | `src/context_composer.py` | ~180 |
| MemoryReasoner | `src/memory_reasoner.py` | ~90 |
| ContextObject | `src/protocol.py` | ~200 |
| FactProjection | `src/projections/fact_state.py` | ~150 |
| PersonProjection | `src/projections/person.py` | ~150 |
| RelationshipProjection | `src/projections/relationship.py` | ~300 |
| TimeContextProjection | `src/projections/time_context.py` | ~350 |
| EmotionProjection | `src/projections/emotion.py` | ~330 |
| GrowthProjection | `src/projections/growth.py` | ~180 |

---

*最后更新: 2026-06-28*
*对应版本: v0.5.0-memory-core*
