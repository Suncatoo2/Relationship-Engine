# Memory 生命周期 — 全局架构视图

> 一条消息从用户输入到 AI 回复，完整经过的每一层。

---

## 完整数据流

```
                        用户输入了一句话
                              │
                              ▼
┌─────────────────────────────────────────────────┐
│ 1. Chat Event                                    │
│    web_server._auto_extract_facts()              │
│    识别陈述句 → 创建 fact event                  │
│    保存 chat event 到 Event Log                   │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 2. Event Log (append-only JSONL)                │
│    所有事件的唯一数据源                           │
│    不可修改，不可删除                             │
└────────────────────┬────────────────────────────┘
                     │  iter_events()
                     ▼
┌─────────────────────────────────────────────────┐
│ 3. Projection Layer                             │
│    8 个 Projection 并行计算（互不依赖）            │
│                                                 │
│    ┌─────────────────┬──────────────────────┐   │
│    │ FactProjection  │ PersonProjection     │   │
│    │ (active facts)  │ (人物画像)            │   │
│    ├─────────────────┼──────────────────────┤   │
│    │ Relationship    │ TimeContext          │   │
│    │ (关系+衰减)      │ (相对时间+密度)       │   │
│    ├─────────────────┼──────────────────────┤   │
│    │ Emotion         │ Growth              │   │
│    │ (情绪趋势)       │ (成长时间线)          │   │
│    ├─────────────────┼──────────────────────┤   │
│    │ Conversation    │ Reminder            │   │
│    │ (对话分析)       │ (智能提醒)           │   │
│    └─────────────────┴──────────────────────┘   │
│                                                 │
│    输出: 8 个 Profile (dataclass + to_dict)      │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 4. Memory Engine (编排层)                        │
│                                                 │
│    FactProjection → active facts                │
│        ↓                                        │
│    Memory Selector (关键词匹配)                   │
│        ↓                                        │
│    断言验证 (同 category 无重复)                   │
│        ↓                                        │
│    Memory Reasoner (v0.4 实现推理)               │
│        ↓                                        │
│    Context Composer (组合所有 Profile)            │
│        ↓                                        │
│    Prompt Builder (结构化 → 文本)                 │
│        ↓                                        │
│    输出: ContextSnapshot + Prompt 文本            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 5. Provider Layer                               │
│    模型无关接入                                  │
│    DeepSeek / Claude / GPT / Gemini              │
│        ↓                                        │
│    流式输出 (SSE)                                │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 6. Response                                     │
│    AI 回复逐字显示                               │
│    + 保存到 Event Log (assistant chat event)     │
│    + 保存到 Prompt Log (完整链路)                 │
└─────────────────────────────────────────────────┘
```

---

## 关键设计决策

### 1. Projection 层为什么是 8 个独立的？

```
原因：互不依赖，各自独立。
好处：
  - 删掉 Emotion，Person 仍然工作
  - 升级 FactProjection 算法，其他不变
  - 未来并行计算多个 Projection（每个线程一个）
```

### 2. Memory Engine 为什么是编排层？

```
原因：Projection 只负责计算，Composer 只负责组合，
      Engine 负责"根据当前问题选择哪些记忆"。
好处：
  - Selector 可以换（关键词 → 语义搜索）
  - 不需要改 Projection
```

### 3. Snapshot 和 Prompt 的区别？

```
Snapshot:  结构化数据（JSON/dict），给 Debug/API 用的
Prompt:    文本，给 LLM 用的
两者永远分开。Prompt Builder 是唯一的转换点。
```

---

## 未来演进方向

```
v0.4:   Memory 分层 (Facts/Preferences/Personality/Emotion)
v0.45:  Memory Reasoner 基础实现
v0.5:   语义搜索 (embedding) + 动态权重
v0.6:   Incremental Projection (百万级事件)
v0.7:   Emotion + Relationship 完整实现
v0.8:   Proactive Memory (AI 主动提醒)
v1.0:   Persona + Story Projection
```
