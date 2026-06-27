# Relationship-Engine

> **AI 不应该只是回答问题，它应该帮你经营所有关系。**

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
Event Log（唯一数据源）
    │
    ▼
Projection Layer（7 个 Projection）
    │  Person / Relationship / Time / Emotion / Growth / Reminder / Conversation
    ▼
Context Composer（组合 + 预算控制）
    │
    ▼
Prompt Builder（LLM 适配层）
    │
    ▼
AI（Claude / GPT / DeepSeek / Qwen）
```

核心设计原则：**Everything is Event, Everything else is Projection.**

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
│   ├── event_log.py             # append-only JSONL 存储
│   ├── provider.py              # LLM Provider Interface
│   ├── mcp_server.py            # MCP Server（7 Write + 5 Read + 2 Resources）
│   ├── web_server.py            # Web Server（SSE 流式 + 会话管理）
│   ├── memory_engine.py         # Memory Engine（记忆引擎）
│   ├── main.py                  # 入口（--web / --http / stdio）
│   ├── web/
│   │   └── chat.html            # ChatGPT 风格聊天界面
│   └── projections/
│       ├── base.py              # Projection 基类
│       ├── person.py            # 人物画像
│       ├── relationship.py      # 关系状态 + 衰减模型
│       ├── time_context.py      # 时间感知
│       ├── emotion.py           # 情绪摘要
│       ├── growth.py            # 成长时间线
│       ├── reminder.py          # 智能提醒
│       ├── conversation.py      # 对话分析
│       ├── context.py           # Context Composer
│       └── prompt_builder.py    # Prompt Builder
├── tests/                       # 249 单元测试 + 47 验收测试
├── docs/
│   ├── Vision.md                # 项目灵魂
│   ├── ROADMAP.md               # 版本路线图
│   ├── ARCHITECTURE.md          # 完整架构设计文档
│   ├── PHASE3_REPORT.md         # Phase 3 发布报告
│   └── SESSION.md               # 开发存档
└── data/                        # 持久化数据（JSONL）
```

---

## 开发进度

| 版本 | 内容 | 状态 |
|------|------|------|
| v0.1 | 聊天（SSE 流式 + Event Log + ChatGPT 风格 UI） | ✅ 完成 |
| v0.2 | Memory Engine（自动读取记忆 + Prompt Log + Debug 面板） | ✅ 完成 |
| v0.3 | Provider Layer（模型无关接入） | 📋 计划中 |
| v0.4 | Relationship Timeline | 📋 计划中 |
| v0.5 | Emotion + Reminder | 📋 计划中 |
| v1.0 | Relationship OS | 🎯 目标 |

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
