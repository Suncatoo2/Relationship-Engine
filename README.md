# Relationship-Engine

> **AI 不应该只是回答问题，它应该帮你经营所有关系。**

> **Relationship Engine is an architecture, not a collection of features.**
> **Every release introduces a new capability, not a new feature.**

```
Architecture Version : v0.7 (Stable)
Implementation Version : v0.4 (In Progress)
```

Relationship-Engine 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 的关系管理引擎，为大语言模型提供长期记忆、人物画像、关系追踪、事件记录、情绪摘要和智能提醒能力。

与传统 AI 的「一次对话，一次遗忘」不同，Relationship-Engine 希望让 AI 能够真正理解人与人的关系，并随着时间不断成长。

无论是朋友、家人、同学、客户还是团队成员，AI 都能够持续记录重要信息、分析关系变化，并在未来的交流中主动利用这些记忆。

---

## 为什么要做这个项目？

现在的大多数 AI 擅长回答问题，却不擅长记住人。

现实生活中的关系不是由一段对话决定，而是由无数次交流、事件和时间共同塑造。

Relationship-Engine 希望成为 AI 的「**关系操作系统（Relationship OS）**」：

- 🧠 **长期人物记忆**（Persistent Memory）
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

## 项目特点

- ✅ 基于 MCP 标准协议
- ✅ 支持 Claude、GPT、DeepSeek、Qwen 等模型
- ✅ 支持 stdio 与 HTTP 两种运行方式
- ✅ 模块化设计，方便扩展
- ✅ 面向长期记忆，而非单轮对话
- ✅ 可作为任何 AI Agent 的关系管理层

---

## 架构

```
用户输入 (Interaction)
      │
      ▼
Pipeline.publish()          ← 唯一写入口
      │
      ├── Storage.append(event)  ← 不可变 Event Log
      └── Dispatcher.dispatch()  ← registry 模式路由
              │
              ▼
Projection Layer (6 个)
  Fact / Person / Relationship / Time / Emotion / Growth
              │
              ▼
ContextComposer
  ├── MemoryReasoner (summary)
  ├── Suggestions (Engine Detects)
  └── ContextObject (标准 JSON)
              │
              ▼
PromptAdapter
  ├── Claude / GPT / DeepSeek
  └── 行为约束（Constraint, 不是 Prose）
              │
              ▼
LLM → 回复
```

**10 条架构原则** · **9 个 ADR** · **6 条交互哲学**

核心设计原则：**Everything is Event, Everything else is Projection.**

详见 [MEMORY_FLOW.md](docs/MEMORY_FLOW.md)

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
| `get_context` | 获取完整 AI 上下文（最核心） |
| `get_person` | 获取人物画像 |
| `get_events` | 获取原始事件流 |
| `get_reminders` | 获取智能提醒 |
| `search` | 搜索所有记忆 |

---

## 快速开始

```bash
# 安装依赖
pip install -e .

# 配置（可选，不配置 LLM 也能用 Tools）
cp .env.example .env

# 本地模式（stdio，配合 Claude Desktop 等）
python -m src.main

# 远程模式（HTTP，部署到服务器，任何 AI 可调用）
python -m src.main --http
```

### Claude Desktop 配置

在 `claude_desktop_config.json` 中添加：

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

### 部署到阿里云

```bash
git clone https://github.com/Suncatoo2/Relationship-Engine.git
cd Relationship-Engine
pip install -e .
cp .env.example .env
python -m src.main --http
```

---

## 项目结构

```
Relationship-Engine/
├── src/
│   ├── event_types.py           # Event 数据结构 + 枚举
│   ├── event_log.py             # append-only JSONL（底层实现）
│   ├── storage.py               # Storage 抽象接口 + JSONLStorage
│   ├── interaction_pipeline.py  # Pipeline（37 行，只做协调）
│   ├── dispatcher.py            # Dispatcher（registry 模式）
│   ├── context_composer.py      # ContextComposer（Projections → ContextObject）
│   ├── memory_engine.py         # Memory Engine（适配层）
│   ├── memory_reasoner.py       # MemoryReasoner（summary + highlights）
│   ├── prompt_adapter.py        # PromptAdapter（Claude/GPT/DeepSeek）
│   ├── snapshot_manager.py      # SnapshotManager（save/load/verify）
│   ├── provider.py              # LLM Provider Interface
│   ├── protocol.py              # ContextObject（frozen API Contract）
│   ├── web_server.py            # Web Server（SSE 流式 + 会话管理）
│   ├── mcp_server.py            # MCP Server（接入 Pipeline）
│   ├── main.py                  # 入口（--web / --http / stdio）
│   ├── web/chat.html            # ChatGPT 风格聊天界面
│   └── projections/             # Projection Layer（6 个）
│       ├── base.py              # Projection 基类（apply + snapshot + info）
│       ├── fact_state.py        # FactProjection
│       ├── person.py            # PersonProjection
│       ├── relationship.py      # Relationship + Lifecycle
│       ├── time_context.py      # TimeContext
│       ├── emotion.py           # Emotion + Momentum
│       ├── growth.py            # Growth
│       ├── reminder.py          # Reminder
│       ├── conversation.py      # Conversation
│       ├── context.py           # Context Composer（旧版）
│       └── prompt_builder.py    # Prompt Builder（旧版）
├── tests/                       # 344 单元测试 + Golden + Regression
│   └── golden/context_object.json
├── examples/
│   └── alice_demo.py            # 端到端演示
├── docs/
│   ├── VISION.md                # 项目灵魂
│   ├── ROADMAP.md               # 版本路线图
│   ├── HANDOFF.md               # 项目交接文档
│   ├── MEMORY_FLOW.md           # 数据流全景图
│   └── architecture/
│       ├── ARCHITECTURE_PRINCIPLES.md   # 10 条原则
│       ├── ARCHITECTURE_DECISIONS.md    # 9 个 ADR
│       ├── INTERACTION_PHILOSOPHY.md    # 6 条交互哲学
│       └── 01_pipeline_architecture.md  # Pipeline 架构设计
└── data/{user_id}/              # 多用户数据隔离
    └── events.jsonl
```

---

## 版本

本项目采用 Architecture–Implementation Dual Lifecycle Versioning（架构—实现双版本体系）。

架构有自己的演进速度。实现有自己的开发速度。两者相互对应，但不要求同步完成。

### Architecture Milestones

| 版本 | 设计内容 | 状态 |
|------|---------|------|
| v0.4 | Protocol & Pipeline Design — Pipeline + Dispatcher + Storage + ADR 1-6 | ✅ |
| v0.5 | Projection Ecosystem Design — ContextComposer + MemoryReasoner + Golden | ✅ |
| v0.6 | Output Layer Design — PromptAdapter + Lifecycle + Momentum + Suggestions | ✅ |
| v0.7 | Performance Design — SnapshotManager + Incremental + Recovery | ✅ |
| v1.0 | Relationship OS Design | 🎯 |

### Implementation Status

| 版本 | 内容 | 状态 |
|------|------|------|
| v0.1 | 聊天（SSE 流式 + Event Log + ChatGPT 风格 UI） | ✅ |
| v0.2 | Memory Engine（自动读取记忆 + Prompt Log + Debug） | ✅ |
| v0.3 | 8 Projections + MCP Server + Context Composer + Provider | ✅ |
| v0.3.99 | Architecture Review（10 份设计文档 + 7 Principles + 5 ADR） | ✅ |
| v0.4 | Infrastructure — Pipeline + Dispatcher + Storage + Event Schema | 🚧 In Progress |
| v0.5 | Memory Core — Reasoner + Goals + Regression + ContextComposer | ⬜ |
| v0.6 | Output Layer — PromptAdapter + Emotion Momentum + Lifecycle | ⬜ |
| v0.7 | Performance — SnapshotManager + Incremental + Recovery | ⬜ |
| v1.0 | Relationship OS MVP | 📋 |

### 测试

344 tests passed (Current Implementation). 覆盖 Infrastructure 到 Performance 的核心路径，不代表覆盖全部 Architecture 设计范围。

### 架构文档

10 Principles · 9 ADRs · Interaction Philosophy · Memory Retrieval Policy

---

## 测试

```bash
# 运行单元测试
python -m pytest tests/ --ignore=tests/acceptance_test.py -v

# 运行验收测试（压力测试 + 场景模拟 + 对抗性测试）
python tests/acceptance_test.py
```

---

## 项目愿景

我们相信，未来 AI 最重要的能力之一，不是更大的模型，而是真正理解人与人之间的关系。

Relationship-Engine 希望成为 AI 世界中的「**Relationship Operating System**」，让每一个 AI 都能够记住重要的人、理解关系、感知时间，并陪伴用户走得更远。

---

## License

MIT
