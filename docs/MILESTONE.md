# Milestone — v0.2 Stable

**日期：** 2026-06-27
**版本：** v0.2-stable
**状态：** ✅ 完成

---

## 当前完成

| 组件 | 说明 |
|------|------|
| Event Log | append-only JSONL，唯一数据源 |
| Memory Engine | 独立模块，自动读取记忆 → Context Composer → Prompt Builder |
| Context Builder | ContextSnapshot（结构化）→ Prompt 文本 |
| Prompt Log | 每次 LLM 调用的完整链路保存 |
| Debug API | /api/debug/context + /api/debug/prompts |
| Debug Panel | 前端 🧠 Memory 按钮，显示 Context |
| Web Server | SSE 流式输出 + 会话管理 + 消息自动保存 |
| Chat UI | ChatGPT 风格深色主题 + Markdown 渲染 + 流式显示 |

---

## 数据流

```
User
  ↓
Web Server (SSE 流式)
  ↓
Memory Engine
  ↓ 读取 Event Log
Context Composer (7 Projections)
  ↓ ContextSnapshot
Prompt Builder
  ↓ Prompt 文本
LLM (当前离线模式)
  ↓
Assistant 回复
  ↓
Event Log (+ Prompt Log)
```

---

## 项目结构

```
src/
├── event_types.py     # Event 数据结构 + 枚举
├── event_log.py       # JSONL 存储 + 迭代器
├── memory_engine.py   # 记忆引擎
├── web_server.py      # Web Server
├── web/chat.html      # 聊天界面
├── mcp_server.py      # MCP Server
├── provider.py        # LLM Provider Interface
├── main.py            # 入口
└── projections/       # 7 个 Projection
```

---

## 测试

| 类型 | 数量 | 状态 |
|------|------|------|
| 单元测试 | 249 | ✅ |
| 验收测试 | 47 | ✅ |
| 端到端测试 | 11 步 | ✅ |

---

## 下一阶段：v0.3 — Provider Layer

**目标：** 接入真实 LLM，Memory 真正参与回答

**验收标准：**
- ❌ 失败：用户问"小雨最近怎么样？"，AI 回复"请问小雨是谁？"
- ✅ 成功：AI 回复"你们已经5天没聊了，上次她说在准备考试"
