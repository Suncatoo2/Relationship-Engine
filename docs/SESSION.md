# Relationship Event OS — 开发存档

**日期：** 2026-06-26
**状态：** Step 1 完成，Step 2 待开始
**分支：** main
**最新 Tag：** v3-rc1

---

## 一、当前完成情况

### Phase 1-3（已完成，v3-rc1）

| Phase | 内容 | 测试 |
|-------|------|------|
| Phase 1 | Event Types + Event Log + Projection Base | 76 tests |
| Phase 2 | 7 Projections（Person/Relationship/Time/Emotion/Growth/Reminder/Conversation） | 139 tests |
| Phase 3 | Context Composer + Prompt Builder + MCP Server | 249 tests |
| 验收测试 | 压力测试 + 场景模拟 + 对抗性测试 | 47/47 passed |

### Step 1（刚完成）

| 组件 | 文件 | 说明 |
|------|------|------|
| Web Server | `src/web_server.py` | FastAPI + SSE 流式输出 + 会话管理 |
| 聊天页面 | `src/web/chat.html` | ChatGPT 风格深色主题 + Markdown + 流式显示 |
| 入口 | `src/main.py` | 支持 `--web` / `--http` / stdio 三种模式 |

**验证结果：**
- ✅ SSE 流式输出正常
- ✅ Markdown 渲染 + 代码高亮
- ✅ 消息自动保存到 Event Log
- ✅ 重启后记忆保留
- ✅ 左侧会话历史
- ✅ Memory Engine 接口已预留（Step 2 填充）

---

## 二、当前项目结构

```
Relationship-Engine/
├── src/
│   ├── event_types.py           # Event 数据结构 + 枚举
│   ├── event_log.py             # append-only JSONL + 迭代器
│   ├── provider.py              # LLM Provider Interface
│   ├── mcp_server.py            # MCP Server（7W + 5R + 2Resources）
│   ├── web_server.py            # Web Server（SSE 流式 + 会话管理）
│   ├── main.py                  # 入口（--web / --http / stdio）
│   ├── web/
│   │   └── chat.html            # ChatGPT 风格聊天界面
│   └── projections/
│       ├── base.py              # Projection 基类
│       ├── person.py            # 人物画像
│       ├── relationship.py      # 关系状态 + 衰减
│       ├── time_context.py      # 时间感知
│       ├── emotion.py           # 情绪摘要
│       ├── growth.py            # 成长时间线
│       ├── reminder.py          # 智能提醒
│       ├── conversation.py      # 对话分析
│       ├── context.py           # Context Composer
│       └── prompt_builder.py    # Prompt Builder
├── data/
│   └── events.jsonl             # Event Log（唯一数据文件）
├── tests/
│   ├── acceptance_test.py       # 验收测试
│   └── test_*.py                # 249 单元测试
├── docs/
│   ├── ARCHITECTURE.md          # 完整架构设计
│   ├── PHASE3_REPORT.md         # Phase 3 发布报告
│   └── SESSION.md               # 本文件
└── pyproject.toml
```

---

## 三、下一步：Step 2 — Memory Engine

### 目标

在 AI 回复之前，自动读取记忆并生成 Context，注入到 LLM 的 system prompt。

### 需要做的事

1. 在 `web_server.py` 的 `build_context()` 函数中填充实际逻辑：
   - 调用 `ContextComposer.compose()` 生成 `ContextSnapshot`
   - 调用 `PromptBuilder.build()` 生成 Context 文本
   - 返回给 `stream_llm_response()` 注入 system prompt

2. 修改 `stream_llm_response()`：
   - 接收 Context 参数
   - 将 Context 注入 system prompt
   - 离线模式下也能看到 Context 内容

3. 测试：
   - 聊天后，AI 回复应该包含之前记忆的信息
   - 重启后，AI 仍然记得之前的内容

### 关键代码位置

```python
# web_server.py 中需要修改的函数：

async def build_context(person_name, conversation_id):
    # TODO: Step 2 实现
    events = list(_event_log.iter_events())
    snapshot = ContextComposer().compose(events, person_name)
    return PromptBuilder("default").build(snapshot)

async def stream_llm_response(message, context, history):
    # TODO: Step 3 接入真实 LLM
    # system_prompt = f"你是关系管理AI...\n\n{context}"
    # messages = [{"role": "user", "content": message}]
    # provider.stream_chat(system_prompt, messages)
```

---

## 四、已知问题

| 编号 | 问题 | 严重程度 | 说明 |
|------|------|---------|------|
| 1 | 离线模式回复是占位文本 | 低 | Step 3 接入真实 LLM 后解决 |
| 2 | 用户消息样式可能不对齐 | 低 | 左右对齐的 CSS 需要微调 |
| 3 | `__pycache__` 和 `data/events.jsonl` 在 git 中 | 低 | .gitignore 需要更新 |
| 4 | 没有删除会话功能 | 低 | Step 4 补充 |

---

## 五、开发原则（已确认）

1. **TDD** — 每完成一个文件必须测试通过
2. **小步提交** — 每完成一个 Step 打 tag
3. **逐文件确认** — 每完成一个文件等用户确认
4. **文档优先** — 先更新 ARCHITECTURE.md 再改代码
5. **Event-first** — 所有数据都是 Event，所有视图都是 Projection
6. **Memory Engine 是核心** — 不是聊天框，是关系操作系统
7. **前端 MVP 用原生 JS，v1.0 迁移 React**

---

## 六、产品北极星

> Relationship Engine 的目标不是创造更聪明的 AI，而是创造一个能够和人一起经历时间的 AI。

---

## 七、开发顺序

```
✅ Step 1:   流式聊天 + Event Log + ChatGPT 风格 UI
⬜ Step 2:   Memory Engine（自动读取记忆 → 生成 Context）
⬜ Step 3:   接入真实 LLM
⬜ Step 4:   历史 + 多会话 + 首页
⬜ Step 5:   Relationship OS 深度集成
⬜ v1.0:     迁移 React
```

---

*存档时间：2026-06-26*
*下次继续：Step 2 — Memory Engine*
