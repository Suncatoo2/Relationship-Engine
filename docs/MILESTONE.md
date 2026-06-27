# Milestone — v0.3 Stable

**日期：** 2026-06-27
**版本：** v0.3-stable
**状态：** ✅ RC Approved

---

## v0.3 能力总结

| 能力 | 说明 |
|------|------|
| ChatGPT 风格聊天 | SSE 流式 + Markdown + 代码高亮 |
| Provider Layer | DeepSeek / Claude / GPT / Gemini（模型无关） |
| Memory Selector | 关键词匹配选择相关记忆 |
| Fact Auto-Extraction | 自动识别用户声明，保存为结构化事实 |
| Conflict Resolution | 同 category 最新值覆盖旧值 |
| Explain API | 查看 AI 使用了哪些记忆 |
| Prompt Log | 完整 prompt 链路保存 |
| Provider Debug | Token/延迟/模型信息 |
| Memory Invariants | 10 条不变量 |
| Memory 状态机 | EXTRACTED → VALIDATED → ACTIVE → CONFLICT → STALE → DEPRECATED → ARCHIVED |
| Memory 生命周期文档 | 完整数据流 + Future Problems |
| RC Review | 代码审计 ✅ + 功能验收 ✅ + 压力测试 30 轮 ✅ |

---

## 下一阶段路线

```
Step 3.9 → Memory Test Suite（20~30 自动化场景）
Step 4   → Memory 分层（Facts / Preferences / Personality / Emotion）
v0.4     → Memory Reasoner（AI 判断记忆类别）
v0.5     → 语义搜索 + Dynamic Importance + Persona Lab
```

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
