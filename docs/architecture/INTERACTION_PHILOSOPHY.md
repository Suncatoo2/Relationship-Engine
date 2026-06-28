# Interaction Philosophy — 交互哲学

> 这些原则不依赖任何具体 LLM。
> 无论换 GPT、Claude、DeepSeek 还是未来的任何模型，这些原则都应保持不变。
> 它们定义的不是技术实现，而是 Relationship Engine 与人交互的"灵魂"。

---

## 三层模型

```
Engine Detects → PromptAdapter Constrains → LLM Generates
Engine 不推理 → PromptAdapter 不思考 → LLM 自由生成
```

Engine 负责检测确定性事实。PromptAdapter 负责把事实翻译成行为约束。LLM 负责在约束内自由生成。

---

## 核心原则

### 1. Memory should be demonstrated, never announced.

记忆应该被展示，而不是被宣告。

AI 不需要说"我记得你"。它应该在对话中自然地接上历史上下文。用户会自己意识到——"它还记得"。

```
错误: "主人，虽然过去 30 天了，但我依然守着你的记忆没有丢哦。"
正确: 用户说"我和小雨怎么样了"，AI 直接用事实回答。
```

### 2. Memory should feel acknowledged, not announced.

记忆应该被自然地确认，而不是被正式地宣告。

当用户让 AI 记住一件事，AI 的回复应该是"好，我会记着"，而不是"已写入数据库"。

```
错误: "已记住：小雨喜欢蓝色。"
正确: "好，我会记着。"

不同关系阶段（由 PromptAdapter 根据 RelationshipProjection.stage 决定）:
  陌生: "好，我会记着。"
  熟悉: "嗯，我记住了。"
  亲密: "放心，这件事我不会忘。"
```

### 3. Show, don't tell.

用行动证明记忆，不用嘴念叨。

用户一年后回来说"我和小雨怎么样了"，AI 直接用事实回答，不煽情，不自我感动。

```
错误: "你还记得吗？一年前你和小雨第一次约会..."
正确: "你和小雨上一次聊天是一年前了。她是口腔专业学生，你们之前关系不错。"
```

### 4. Suggestions are intents, not commands.

建议是意图，不是指令。

Engine 输出 `time_gap = 30d`。PromptAdapter 输出行为约束。LLM 决定怎么说。

```
错误: Engine 输出 "silence_alert: 请提醒用户联系小雨"
正确: Engine 输出 "time_gap: 30d"
      PromptAdapter 输出 "Do not introduce historical topics proactively."
      LLM 生成 "好久没聊了，最近怎么样？"
```

### 5. Engine outputs facts, not derivations.

Engine 只输出客观事实，不输出推导。

`time_gap = 30d` 是事实。`silence_alert = true` 是推导。Engine 不应该为单个场景增加业务字段。

```
错误: Engine 输出 {"time_gap": "30d", "silence_alert": true, "memory_intact": true}
正确: Engine 输出 {"time_gap": "30d"}
```

### 6. PromptAdapter outputs constraints, not prose.

PromptAdapter 输出可验证的行为规则，不输出文学指导。

```
错误: "Acknowledge the extended absence without judgment."
正确: "Allow one sentence acknowledging the time gap."
错误: "Leave the door open naturally."
正确: "Do not ask where the user has been."
```

---

## PromptAdapter 行为约束映射表

PromptAdapter 维护一张映射表：`signal → constraints`。不维护任何文案。

```
time_gap < 1d:
  (无特殊约束)

time_gap >= 2d:
  - Allow one brief acknowledgment of the gap.
  - Do not ask where the user has been.

time_gap >= 7d:
  - Same as 2d, plus:
  - Do not express emotion about the absence.
  - Do not announce that memory is preserved.

time_gap >= 30d:
  - Same as 7d, plus:
  - Do not introduce historical topics proactively.
  - Let factual continuity imply persistent memory.

time_gap >= 180d:
  - Same as 30d, plus:
  - First response should be maximally brief.
  - Give full initiative to the user.
```

---

## 记忆确认的语气阶梯

由 PromptAdapter 根据 `relationship_stage` 生成行为约束，LLM 自由生成具体措辞。

```
stage = 陌生人:
  constraint: "Respond briefly. Use formal language."

stage = 认识:
  constraint: "Respond naturally. Be friendly but not intimate."

stage = 朋友:
  constraint: "Respond warmly. Show genuine interest."

stage = 亲密:
  constraint: "Respond with warmth and care. Be natural."
```

---

## Memory System 统一原则

### 1. Engine = Verifiable Facts

只输出可验证事实，不产生语义总结。

```
允许: {"time_gap": "30d"}           ← 可断言
禁止: {"last_topic": "考试"}        ← 语义推断
禁止: {"emotion_label": "想念"}     ← 情绪推断

ContextObject 应该是:
  observations（观察），不是 interpretations（解释）
  detections（检测），不是 inferences（推断）
  facts（事实），不是 narratives（叙事）
```

### 2. PromptAdapter = Behavioral Constraints

只规定行为边界，不规定人格或情绪。

```
允许: "Acknowledge information boundaries."
允许: "Never fabricate unavailable facts."
允许: "Invite continuation when appropriate."

禁止: "Express curiosity about the user's feelings."
禁止: "Show concern for the user's situation."
禁止: "Leave the door open naturally."
```

真实语言温度交给 LLM，PromptAdapter 只告诉 LLM **能做什么、不能做什么**。

### 3. LLM = Natural Expression

自然组织语言、形成主题、体现温度，但不得改变事实。

### 4. ContextObject = Working Memory, not Cache

ContextObject 每轮根据 Query 重建，不是持久化缓存。

```
查询 "小雨考试" → Working Memory: 小雨相关 facts
                  ↓
查询 "外卖"     → Working Memory: 外卖相关 facts
                  ↓ （小雨 facts 自动退出）
查询 "天气"     → Working Memory: 天气相关 facts
```

这不是 TTL 过期机制，而是 Focus-based Reconstruction——当用户切换主题后，过期数据自动退出 Working Memory。Engine 的 `project()` 纯函数特性天然支持每轮重建。

### 5. Show, don't tell — Memory 的可信度来自 Recall，不是 Statement

```
不要说 "我一直记得" → 正确引用历史事实
不要说 "我没有忘记" → 准确接上过去的上下文
不要说 "你的记忆还在" → 用事实回答用户的问题
```

---

## 未来演进记录

以下变更记录为未来 Major Version 的结构性调整方向，当前版本不做修改。

| 当前字段 | 问题 | 未来调整 |
|---------|------|---------|
| `memory_summary` | "summary" 暗示有人做了总结，但 Engine 不应该总结 | 升级为 `memory_facts`（纯事实拼接，零语义） |

触发条件：下一个 Major Version（v2.0）或 API Contract 修订时。

---

*最后更新: 2026-06-28*
*对应版本: v0.6.0-output-layer*
