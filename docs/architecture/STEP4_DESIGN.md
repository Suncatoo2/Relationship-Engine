# Step 4 — Interaction Pipeline：设计方案

> 不是 Timeline, 不是 Emotion，是建立整个系统的主干。

---

## 为什么 Timeline 不是一个版本

Timeline、Emotion、Growth、Relationship 全部是 **Projection**，不是 Feature。它们应该挂在总线下面，而不是单独成为版本号。

```
错误:
  v0.4: Timeline
  v0.5: Emotion
  → 每个 Feature 一个版本，总线没建好之前 Feature 都是孤立的

正确:
  v0.4: Interaction Pipeline (总线)
  v0.5: 往总线上挂 Projection (Relationship / Emotion / Growth / Timeline)
  → 总线建好后，加 Projection 像插 USB
```

---

## v0.4 交付物

### 1. InteractionPipeline（统一入口）

```python
pipeline = InteractionPipeline(storage, projections)

# 唯一入口
pipeline.publish(interaction)
```

### 2. ProjectionDispatcher（插件化分发）

```python
dispatcher = ProjectionDispatcher([FactProjection(), PersonProjection(), ...])
dispatcher.register(NewProjection())  # 一行注册
```

### 3. Interaction Schema（LLM 输出结构）

```python
@dataclass
class Interaction:
    type: str                 # "chat" | "statement" | "emotion"
    message: str               # 原始消息
    person: str                # 涉及的人物
    facts: list[FactInput]     # LLM 提取的事实
    emotion: EmotionInput | None
    relation_change: RelationInput | None
```

### 4. Storage 接口化

EventLog 改为调用 Storage 接口，而不是直接读写文件。

---

## v0.5 及以后：Projection 扩展

v0.5 不是"做 Emotion Engine"，而是**往总线上挂新的 Projection**：

```
dispatcher.register(RelationshipProjection())
dispatcher.register(EmotionProjection())
dispatcher.register(GrowthProjection())
dispatcher.register(TimelineProjection())
```

每个 Projection 独立计算，互不依赖。和 v0.4 的 FactProjection 完全相同的接口。

---

## v0.7: Prompt Adapter Layer（重要）

```
Context Object (结构化)
      │
      ├──→ Claude Adapter → Claude XML Prompt
      ├──→ GPT Adapter    → GPT Markdown Prompt
      ├──→ Gemini Adapter → Gemini JSON Prompt
      ├──→ Qwen Adapter   → Qwen Text Prompt
      └──→ DeepSeek Adapter → DeepSeek Prompt
```

Memory 只输出结构化 Context Object。Adapter 负责拼成对应的 Prompt 格式。支持新模型 = 加一个 Adapter，不改 Memory Engine。

这个已经有基础：`prompt_builder.py` 里的 DefaultBuilder / GPTBuilder / ClaudeBuilder / DeepSeekBuilder。只需要把入口改成先输出 Context Object 再转 Prompt。
