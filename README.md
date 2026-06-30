# Relationship-Engine

> **Architecture Manifesto**
>
> Relationship OS is not a memory library — it is an AI interaction operating system.
> The Engine owns facts and decisions; the LLM owns expression.
> Every new capability must preserve this separation.
> ContextObject is working memory, not cache. Storage is append-only, not mutable.
> Memory should be demonstrated, never announced.

> **Relationship Engine is an architecture, not a collection of features.**
> **Every release introduces a new capability, not a new feature.**

```
Engine Version : v1.0 (Frozen)
Product Version : v1.0.0-baseline (Stable)
```

Relationship-Engine 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 的关系管理引擎，为大语言模型提供长期记忆、人物画像、关系追踪、事件记录、情绪摘要和智能提醒能力。

与传统 AI 的「一次对话，一次遗忘」不同，Relationship-Engine 让 AI 能够真正理解人与人的关系，并随着时间不断成长。

---

## 为什么要做这个项目？

现在的大多数 AI 擅长回答问题，却不擅长记住人。

现实生活中的关系不是由一段对话决定，而是由无数次交流、事件和时间共同塑造。

Relationship-Engine 希望成为 AI 的「**关系操作系统（Relationship OS）**」：

- 🧠 **长期人物记忆**（Persistent Memory）
- 🔍 **查询感知召回**（Query-Aware Recall）— 相关性排序 + token 预算
- 👤 **自动构建人物画像**（Person Profile）
- ❤️ **关系状态管理**（Relationship Tracking）
- 💬 **对话历史分析**（Conversation Analysis）
- 📅 **时间感知与智能提醒**（Time-aware Reminders）
- 📈 **关系成长时间线**（Relationship Timeline）
- 😊 **情绪变化摘要**（Emotion Summary）

---

## 核心理念

AI 不应该只会回答：

> 「你好，我能帮助你什么？」

它更应该能够说：

> 「欢迎回来。上次我们聊到你的口腔数字化项目，最近进展怎么样？」

真正优秀的 AI，不只是拥有知识，而是能够随着时间建立信任、积累记忆，并陪伴用户成长。

---

## 架构

```
用户输入 (Interaction)
      │
      ▼
Pipeline.publish()          ← 唯一写入口
      │
      ├── Storage.append(event)  ← 不可变 Event Log (WAL + atomic write)
      └── Dispatcher.dispatch()  ← registry 模式路由
              │
              ▼
Projection Layer (9 个)
  Fact / Person / Relationship / Time / Emotion / Growth
  Conversation / Reminder / Profile
              │
              ▼
RetrievalRanker             ← query-aware ranking + token budgeting
              │
              ▼
ContextComposer
  ├── MemoryReasoner (summary)
  ├── Suggestions (Engine Detects)
  └── ContextObject (frozen JSON contract)
              │
              ▼
PromptAdapter
  ├── Claude / GPT / DeepSeek
  └── 行为约束（Constraint, 不是 Prose）
              │
              ▼
LLM → 回复 → Pipeline.publish() ← 闭环
```

**15 条架构原则** · **15 个 ADR** · **10 种事件类型**

核心设计原则：**Everything is Event, Everything else is Projection.**

详见 [MEMORY_FLOW.md](docs/MEMORY_FLOW.md)

---

## Product 1.0 Roadmap

| Step | 名称 | 输入 | 输出 | 状态 |
|------|------|------|------|------|
| 1 | ProfileProjection | person + profile events | 长期关系档案（9th Projection） | ✅ |
| 2 | Memory Retrieval & Ranking | query + facts + max_tokens | 排序后的 ScoredFact 列表 | ✅ |
| 3 | Cross-Projection Reasoning | 9 projections | 跨投影关联洞察 | 📋 |
| 4 | Closed Feedback Loop | LLM 输出 → publish → recall | 状态自动更新 | 📋 |
| 5 | Self Evolution | 用户反馈数据 | 自适应优化 | ⏳ Design Only |

### Engine 1.0（已冻结）

- Event Sourcing (JSONL + WAL + atomic write + crash recovery)
- 9 Projections (all with apply/snapshot incremental interface)
- Pipeline (single entry/exit point, capability guard)
- PipelineResponse (context/metadata/diagnostics)
- Observability (dispatch timing, health, dead letters)
- 15 ADRs documented and enforced

---

## MCP Tools

### Write Tools（写入事件）

| Tool | 说明 |
|------|------|
| `add_person` | 添加人物（姓名、生日、标签、备注） |
| `remember` | 记住关于某人的事实 |
| `add_chat` | 记录聊天消息（支持话题标签） |
| `add_emotion` | 记录情绪数据 |
| `update_relation` | 更新关系阶段和好感度 |
| `add_milestone` | 记录关系里程碑 |
| `add_growth` | 记录成长节点 |

### Read Tools（读取视图）

| Tool | 说明 |
|------|------|
| `get_context` | 获取完整 AI 上下文（支持 query + max_tokens） |
| `get_person` | 获取人物画像 |
| `get_events` | 获取原始事件流 |
| `get_reminders` | 获取智能提醒 |
| `search` | 搜索所有记忆 |

---

## 快速开始

```bash
pip install -e .
cp .env.example .env

# stdio 模式（Claude Desktop 等）
python -m src.main

# HTTP 模式（部署到服务器）
python -m src.main --http
```

### Claude Desktop 配置

```json
{
    "mcpServers": {
        "relationship-engine": {
            "command": "python",
            "args": ["-m", "src.main"],
            "cwd": "/path/to/Relationship-Engine"
        }
    }
}
```

---

## 项目结构

```
Relationship-Engine/
├── src/
│   ├── event_types.py           # Event 数据结构 + 10 types
│   ├── storage.py               # Storage ABC + JSONLStorage (WAL + capability guard)
│   ├── interaction_pipeline.py  # Pipeline (唯一入口, ~370 行)
│   ├── dispatcher.py            # Dispatcher (registry + observability)
│   ├── retrieval_ranker.py      # RetrievalRanker (query-aware + token budget)
│   ├── context_composer.py      # ContextComposer (Projections → ContextObject)
│   ├── protocol.py              # ContextObject + 9 Blocks (frozen API Contract)
│   ├── pipeline_response.py     # PipelineResponse (context/metadata/diagnostics)
│   ├── memory_reasoner.py       # MemoryReasoner (summary + highlights)
│   ├── snapshot_manager.py      # SnapshotManager (save/load/verify)
│   ├── prompt_adapter.py        # PromptAdapter (Claude/GPT/DeepSeek)
│   ├── provider.py              # LLM Provider Interface
│   ├── boundary_policy.py       # BoundaryPolicy (knowledge boundary injection)
│   ├── web_server.py            # Web Server (SSE 流式 + 会话管理)
│   ├── mcp_server.py            # MCP Server (接入 Pipeline)
│   ├── main.py                  # 入口（--web / --http / stdio）
│   ├── web/chat.html            # ChatGPT 风格聊天界面
│   └── projections/             # 9 Projections
│       ├── base.py              # Projection 基类
│       ├── fact_state.py        # FactProjection
│       ├── person.py            # PersonProjection
│       ├── relationship.py      # Relationship + Lifecycle
│       ├── time_context.py      # TimeContext
│       ├── emotion.py           # Emotion + Momentum
│       ├── growth.py            # Growth
│       ├── reminder.py          # Reminder
│       ├── conversation.py      # Conversation
│       └── profile.py           # Profile (1.0 Step 1)
├── tests/                       # 447 tests (0.73s)
│   ├── architecture/            # Architecture compliance tests
│   └── golden/                  # Golden context output
├── examples/
│   └── alice_demo.py            # 端到端演示
├── docs/
│   ├── VISION.md                # 项目灵魂
│   ├── ROADMAP.md               # 产品路线图
│   ├── HANDOFF.md               # 项目交接文档
│   ├── MEMORY_FLOW.md           # 数据流全景图
│   └── architecture/
│       └── ARCHITECTURE_DECISIONS.md  # 15 ADRs
└── data/{user_id}/              # 多用户数据隔离
    └── events.jsonl
```

---

## 测试

```bash
# 全部测试
python -m pytest tests/ -v

# 跳过验收测试
python -m pytest tests/ --ignore=tests/acceptance_test.py -v

# 验收测试（压力测试 + 场景模拟）
python tests/acceptance_test.py
```

---

## 项目愿景

我们相信，未来 AI 最重要的能力之一，不是更大的模型，而是真正理解人与人之间的关系。

Relationship-Engine 希望成为 AI 世界中的「**Relationship Operating System**」，让每一个 AI 都能够记住重要的人、理解关系、感知时间，并陪伴用户走得更远。

---

## License

MIT
