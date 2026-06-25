# Relationship-Engine

> AI 不应该只是回答问题——它应该帮你经营所有关系。

## 这是什么？

一个 **MCP Server**，为任何 AI 提供关系管理能力。

不绑定任何 LLM，通过标准 MCP 协议，DeepSeek、Qwen、GPT、Claude 都能调用。

### 核心能力

| Tool | 功能 |
|------|------|
| `add_person` | 添加人物（姓名、关系类型、生日、备注） |
| `remember` | 记住关于某人的任何信息 |
| `add_chat_message` | 记录聊天消息 |
| `update_relationship` | 更新关系阶段、好感度、事件 |
| `query_person` | 查询某人完整信息 |
| `get_reminders` | 获取提醒（生日、失联警告） |
| `search_memory` | 搜索所有记忆 |

## 架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   DeepSeek  │     │    Claude   │     │     GPT     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────┬───────────┘
                   │               │
            ┌──────▼──────┐ ┌─────▼──────┐
            │  CC Switch  │ │ MCP 协议   │
            │  (LLM 网关)  │ │ (直接调用)  │
            └──────┬──────┘ └─────┬──────┘
                   │               │
                   └───────┬───────┘
                           │
                  ┌────────▼────────┐
                  │ Relationship    │
                  │ Engine MCP      │
                  │ Server          │
                  ├─────────────────┤
                  │ • Memory 人物记忆│
                  │ • Relationship  │
                  │ • Conversation  │
                  │ • Reminders     │
                  └─────────────────┘
```

## 快速开始

```bash
# 安装依赖
pip install -e .

# 配置
cp .env.example .env
# 编辑 .env（可选，不配置 LLM 也能用 Tools）

# 本地模式（stdio，配合 Claude Desktop 等）
python -m src.main

# 远程模式（HTTP，部署到服务器，任何 AI 可调用）
python -m src.main --http
```

## 接入方式

### 方式一：Claude Desktop（stdio）

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

### 方式二：远程 HTTP（任何 AI）

部署到服务器后，任何支持 MCP 的 AI 客户端连接：

```
http://your-server:8080/mcp
```

### 方式三：CC Switch 网关

通过 CC Switch 统一管理 LLM 调用，在 `.env` 中配置：

```
CC_SWITCH_BASE_URL=https://your-ccswitch/v1
CC_SWITCH_API_KEY=your-key
CC_SWITCH_MODEL=deepseek-chat
```

## 项目结构

```
Relationship-Engine/
├── src/
│   ├── memory/          # 人物画像 + 事实记忆
│   ├── relationship/    # 关系追踪 + 好感度 + 提醒
│   ├── conversation/    # 对话历史
│   ├── provider.py      # LLM Provider Interface（CC Switch）
│   ├── mcp_server.py    # MCP Server（7 Tools + 2 Resources）
│   └── main.py          # 入口（stdio / HTTP）
├── data/                # 持久化数据（JSON）
└── .env.example         # 配置模板
```

## 部署到阿里云

```bash
# 在服务器上
git clone https://github.com/Suncatoo2/Relationship-Engine.git
cd Relationship-Engine
pip install -e .
cp .env.example .env
# 编辑 .env 配置 CC Switch

# 启动 HTTP 模式
python -m src.main --http
```

然后在阿里云安全组开放端口（默认 8080）。

## License

MIT
