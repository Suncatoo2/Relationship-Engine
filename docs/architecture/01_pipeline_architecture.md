# 01 — Pipeline Architecture：项目基调

> Relationship Engine 是一条确定性的管道。LLM 负责不确定性，Engine 负责确定性。

---

## Design Philosophy（设计哲学）

### 三句话定义职责边界

> **Memory 保存历史（History），Projection 计算状态（State），Context 服务推理（Reasoning）。**

- **Memory**：忠实记录发生过什么，永远不修改历史
- **Projection**：根据历史计算出当前状态，可以随时重建
- **Context**：从当前状态中提炼出最值得 LLM 知道的信息，而不是把所有数据一股脑塞给模型

---

### Engine never competes with LLM for thinking

```
LLM（不确定性）               Engine（确定性）
──────────────────────────────────────────────────
理解自然语言            →     不碰语义
判断情绪                →     不猜情绪
判断重要性              →     不自己加权
判断关系变化             →     不推断关系
决定回复内容             →     不生成文本

Schema Validation       ←     验证数据结构
Event Persistence       ←     存储不可变
Projection              ←     计算视图
Snapshot                ←     持久化快照
Context Assembly        ←     组装上下文
Storage                 ←     抽象存储层
```

**Engine 是 LLM 的手和脚，不是第二个大脑。**

### 核心理念

1. **Everything is Event** — 所有输入都是事件，所有输出都是投影
2. **Projection is Stateless + Immutable** — 纯函数，输入决定输出
3. **Storage is Abstracted** — 业务逻辑不知道底层存储是什么
4. **One Entry Point** — `publish_interaction()` 是唯一的入口

---

## 2. The Pipeline Lifecycle（生命周期）

```
用户输入一句话
      │
      ▼
┌─────────────────────────────────────────────────┐
│ LLM 判断                                        │
│  • 这是什么类型的消息？（陈述/问题/情绪/闲聊）         │
│  • 含有什么事实？（记住/更新/否定）                  │
│  • 情绪是什么？（开心/焦虑/平静）                   │
│  • 重要吗？（1-10）                                │
│  • 涉及谁？（小雨/老王/自己）                       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ publish_interaction()  ← 唯一入口                 │
│                                                 │
│  interaction = {                                │
│    type: "statement",                           │
│    facts: [{content, category, confidence}],    │
│    emotion: {valence, label},                   │
│    person: "小旭",                              │
│    message: "我最喜欢蓝色",                       │
│  }                                              │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Storage Layer                                   │
│  storage.append(chat_event)  ← 不可变            │
│  storage.append(fact_event)  ← 不可变            │
│  storage.append(emotion_event) ← 不可变           │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Projection Dispatcher                           │
│                                                 │
│  for proj in projections:                       │
│      proj.apply(event)  ← 插件化                 │
│                                                 │
│  ┌────────────┬────────────┬──────────────┐    │
│  │ Fact       │ Person     │ Relationship │    │
│  ├────────────┼────────────┼──────────────┤    │
│  │ Emotion    │ Growth     │ Conversation │    │
│  ├────────────┼────────────┼──────────────┤    │
│  │ Time       │ Reminder   │ (未来扩展...)  │    │
│  └────────────┴────────────┴──────────────┘    │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Snapshot（可选，v0.4.5）                         │
│  dispatcher.snapshot_all() → {projection: state}│
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Context Assembly                                │
│  Memory Engine → Selector → Composer → Builder  │
│  输出: ContextSnapshot + Prompt 文本             │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Provider Layer → LLM                            │
│  流式返回 AI 回复                                │
└─────────────────────────────────────────────────┘
```

---

## 3. Responsibilities（职责边界）

### LLM 负责（不确定性）

```
✓ 理解自然语言含义
✓ 判断用户情绪（valence + label）
✓ 判断是否有新事实需要记录
✓ 判断事实的重要性（importance 1-10）
✓ 判断关系是否发生了变化
✓ 提取结构化信息（content, category, confidence）
✓ 决定如何回复
```

### LLM 不负责

```
✗ 数据一致性保证
✗ 事实去重
✗ Snapshot 管理
✗ Projection 计算
✗ Storage 读写
✗ Context 组装（那是 Engine 的事）
✗ 性能优化
```

### Engine 负责（确定性）

```
✓ Schema Validation（检查 LLM 输出的结构）
✓ Event Persistence（append-only 存储）
✓ Projection（从 events 计算视图）
✓ Snapshot（定期保存快照）
✓ Context Assembly（组装给 LLM 的上下文）
✓ Storage Abstraction（屏蔽存储细节）
✓ Conflict Resolution（同 category 去重）
```

### Engine 不负责

```
✗ 推理
✗ 猜测
✗ 情绪判断
✗ 内容生成
✗ 自然语言理解
```

---

## 4. Interaction API（高层接口）

### Engine 对外只有一个入口

```python
def publish_interaction(interaction: Interaction) -> InteractionResult:
    """所有交互的唯一入口

    Args:
        interaction: LLM 结构化后的交互数据

    Returns:
        InteractionResult: event_ids + snapshot + context
    """
```

### Interaction 数据结构

```python
@dataclass
class Interaction:
    type: str                          # "statement" | "question" | "emotion" | "chat"
    message: str                        # 原始用户消息
    person: str                         # 涉及的人物
    facts: list[FactInput]              # LLM 提取的事实（可选）
    emotion: EmotionInput | None        # LLM 判断的情绪（可选）
    relation_change: RelationInput | None  # LLM 判断的关系变化（可选）

@dataclass
class FactInput:
    content: str
    category: str
    importance: int = 5
    confidence: float = 0.9
```

### 这不是"合并 MCP Tools"

这是让 LLM 自己决定"这次交互产生了什么"，然后一次性交给 Engine。

MCP Tools 是给外部 AI 调用的低层接口。
`publish_interaction()` 是 Engine 内部的高层入口。

---

## 5. Storage Abstraction（存储抽象）

见 [STORAGE_ABSTRACTION.md](./STORAGE_ABSTRACTION.md)

当前选择 JSONL 的原因：
- 人类可读
- append-only（不会被 crash 损坏）
- git 友好
- 数据量 < 10 万时性能完全够用

---

## 6. Evolution（演进路线）

### Today (v0.3.95)

```
LLM (DeepSeek)
    ↓
web_server (手动提取 fact + 写 Event)
    ↓
Memory Engine (手动 replay + 组合)
    ↓
Context → LLM 回复
```

### v0.4 (Interaction Pipeline)

```
LLM → publish_interaction() → Dispatcher → 8 Projections
                                          → Memory Engine
                                          → Context → LLM 回复
```

### v0.6 (Agent-ready)

```
User → Planner Agent（多步骤规划）
         ↓
       Worker Agents（并行执行）
         ↓
       publish_interaction() × N
         ↓
       Engine（确定性管道）
         ↓
       Context → Planner → 回复
```

### v1.0 (Relationship OS)

```
任何 AI（LLM / Agent / 用户）
    ↓
publish_interaction()  ← 唯一入口
    ↓
Engine = 确定性管道
    ↓
任何模型（DeepSeek / Claude / GPT / Gemini）
```

---

*底线：Engine never competes with LLM for thinking.*
