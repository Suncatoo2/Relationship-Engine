# Step 4 — Interaction Pipeline + Context Contract v1

> 四个阶段，不是版本号。

---

## 开发阶段

```
Phase 1: Protocol（协议）
  统一语言：Context Object / Event Schema / Projection Interface / Storage Interface
  目标：所有模块说同一种语言

Phase 2: Pipeline（流水线）
  publish → EventBus → Dispatcher → Projection → Snapshot → ContextComposer
  目标：跑通全链路，哪怕只有一个 Projection

Phase 3: Projection Ecosystem
  Relationship / Emotion / Growth / Timeline / Goals / Reminder...
  目标：插拔式挂载，不改 Pipeline

Phase 4: Prompt Adapter
  Context Object → Claude / GPT / Gemini / DeepSeek Prompt
  目标：上下文先稳定，Adapter 最后做
```

---

## Context Composer — 最关键的一层

Context 不是数据库 dump。

Context 应该回答一个问题：**"如果我是 AI，现在最应该知道什么？"**

```
错误（Memory Dump）:
  用户有 3000 条聊天记录 → 全部塞进 Prompt

正确（Current World State）:
  最近 7 天发生了什么？
  现在情绪怎么样？
  最近最重要的人是谁？
  正在推进哪个项目？
  今天有没有要提醒？
```

### Composer 的真正职责

```
Projection Outputs（原始数据）
    │
    ▼
Context Composer
    ├── 筛选（哪些信息现在最重要？）
    ├── 排序（按相关性排列）
    ├── 摘要（把 raw data 变成 LLM 友好的叙述）
    └── 压缩（Token 预算内，只保留最重要的）
    │
    ▼
Context Object（当前世界状态）
```

---

## 第一章：Context Contract v1（最终输出）

Pipeline 最终就是为了产生 Context。如果不知道最终输出长什么样，Pipeline 容易越写越偏。

### Context Object v1

```python
@dataclass
class ContextObject:
    """Memory Engine 输出给所有 LLM 的统一协议"""
    identity: IdentityBlock           # must: 这是谁
    memory: MemoryBlock               # must: 我知道什么
    relationship: RelationshipBlock   # must: 关系怎样
    time: TimeBlock                   # must: 时间感知
    emotion: EmotionBlock | None      # optional
    growth: GrowthBlock | None        # optional
    reminders: list | None            # optional
    metadata: ContextMetadata         # must: 元数据
```

### 4 个必须 Block

```python
@dataclass
class IdentityBlock:
    name: str
    nickname: str
    tags: list[str]
    birthday: str
    days_known: int

@dataclass
class MemoryBlock:
    active_facts: list[FactItem]         # 当前活跃的事实
    fact_count: int
    memory_summary: str                  # LLM-ready: "关于这个人，你记住..."
    top_topics: list[str]                # 最近话题

@dataclass
class RelationshipBlock:
    stage: str
    chemistry: int
    decay_chemistry: int
    trend: str
    last_contact_summary: str            # "3天前聊过"
    milestones: list[str]                # 最近里程碑

@dataclass
class TimeBlock:
    last_chat_label: str                 # "今天" / "3天前" / "一周前"
    silence_label: str                   # "刚聊完" / "几天没聊" / "很久没联系"
    upcoming: list[str]                  # ["生日还有5天"]
    days_known: int
```

### LLM-ready 摘要格式

关键的工程决策：不是把 raw data 塞给 LLM，而是生成 LLM 友好的叙述性摘要。

```
错误: density_7d = {period_days: 7, event_count: 42, daily_avg: 6.0, label: "很密集"}
正确: memory_summary = "你们最近一周聊得很频繁，几乎每天都有联系"
```

---

## 第二章：Interaction Pipeline 接口

先定 API，里面全是 `pass`。以后实现随便改，API 不改。

```python
class InteractionPipeline:
    """所有交互的唯一入口"""

    def publish(self, interaction: Interaction) -> str:
        """发布一个交互 → 写入 Event Log → 分发到所有 Projection
        Returns: event_id
        """
        ...

    def recall(self, person: str, query: str = "") -> ContextObject:
        """为某个人构建完整的记忆上下文
        Returns: ContextObject（不包含 Prompt 文本）
        """
        ...

    def snapshot(self) -> dict[str, dict]:
        """获取所有 Projection 的当前快照"""
        ...

    def rebuild(self, person: str = None):
        """从 Event Log 重建所有 Projection"""
        ...
```

### Interaction Schema

```python
@dataclass
class Interaction:
    """LLM 结构化后的交互数据"""
    type: str                           # "chat" | "statement" | "emotion"
    message: str                        # 原始用户消息
    person: str                         # 涉及的人物
    facts: list[FactInput]              # LLM 提取的事实
    emotion: EmotionInput | None        # LLM 判断的情绪
    relation_change: RelationInput | None

@dataclass
class FactInput:
    content: str
    category: str
    importance: int = 5
    confidence: float = 0.9
```

### Projection Dispatcher

```python
class ProjectionDispatcher:
    """投影分发器 — 插件化"""

    def register(self, projection: Projection):
        """注册一个新的 Projection"""
        ...

    def dispatch(self, event: Event):
        """分发事件到所有 Projection"""
        ...

    def snapshot_all(self) -> dict[str, dict]:
        """所有 Projection 的快照"""
        ...
```

---

## 第三章：Prompt Adapter Layer

```
Context Object (结构化)
      │
      ├──→ Claude Adapter → Claude XML Prompt
      ├──→ GPT Adapter    → GPT Markdown Prompt
      ├──→ Gemini Adapter → Gemini JSON Prompt
      ├──→ Qwen Adapter   → Qwen Text Prompt
      └──→ DeepSeek Adapter → DeepSeek Prompt
```

Memory Engine 只输出 Context Object。加新模型 = 加一个 Adapter。

### Adapter 接口

```python
class PromptAdapter(ABC):
    @abstractmethod
    def build(self, context: ContextObject) -> str:
        """把 Context Object 变成 LLM 可消费的 Prompt 文本"""
        ...
```

---

## 数据流总览

```
User Chat
    │
    ▼
publish(interaction)
    │
    ├──→ Storage.append(event)        ← Event Log (不可变)
    │
    └──→ Dispatcher.dispatch(event)
            │
            ├──→ FactProjection.apply()
            ├──→ PersonProjection.apply()
            ├──→ RelationshipProjection.apply()
            ├──→ (所有 8 个 Projection)
            │
            ▼
         Snapshot（可选）
            │
            ▼
    recall(person, query)
            │
            ├──→ Memory Selector（筛选相关 facts）
            ├──→ Context Assembler（组装 Context Object）
            │
            ▼
         Context Object
            │
            ├──→ Claude Adapter → Prompt
            ├──→ GPT Adapter    → Prompt
            └──→ ...
                     │
                     ▼
                  LLM → 回复
```
