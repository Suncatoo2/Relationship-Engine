"""Relationship Event OS — Web Server (Step 1)

架构：
  用户消息 → Memory Engine（预留） → LLM Provider → SSE 流式返回
  每条消息自动保存到 Event Log。

Step 1: 流式聊天 + Event Log
Step 2: 填充 Memory Engine（自动读取记忆 → 生成 Context）
Step 3: 接入真实 LLM
"""

import os
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from .event_types import create_event, EventType
from .event_log import EventLog


# ---- 全局实例 ----

_data_dir = os.getenv("DATA_DIR", "data")
_event_log = EventLog(_data_dir)

app = FastAPI(title="Relationship Event OS")
WEB_DIR = Path(__file__).parent / "web"


# ---- 数据模型 ----

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"
    person_name: str = ""


class ConversationInfo(BaseModel):
    id: str
    title: str
    person_name: str
    last_message: str
    updated_at: str


# ---- Memory Engine 接口（Step 2 填充） ----

async def build_context(person_name: str, conversation_id: str) -> str:
    """构建发送给 LLM 的 Context。

    Step 1: 返回空 Context（离线模式）
    Step 2: 调用 Context Composer，注入记忆
    """
    # TODO: Step 2 实现
    # events = list(_event_log.iter_events())
    # snapshot = ContextComposer().compose(events, person_name)
    # return PromptBuilder().build(snapshot)
    return ""


async def stream_llm_response(message: str, context: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """流式调用 LLM。

    Step 1: 离线模式，模拟流式输出
    Step 3: 接入真实 LLM Provider
    """
    # TODO: Step 3 替换为真实 LLM
    # provider = create_provider()
    # async for chunk in provider.stream_chat(system_prompt, messages):
    #     yield chunk

    # 离线模式：模拟流式回复
    reply = generate_offline_reply(message, history)
    for char in reply:
        yield char
        await asyncio.sleep(0.02)


def generate_offline_reply(message: str, history: list[dict]) -> str:
    """离线模式的智能回复（不需要 LLM）"""
    msg = message.strip().lower()

    if not history:
        return f"你好！这是我们第一次聊天。\n\n你刚才说了：「{message}」\n\n我记住了。以后配置好 API Key，我就能真正理解你、记住你，并随着时间陪伴你成长。"

    if "你好" in msg or "hi" in msg or "hello" in msg:
        return f"你好！我们已经聊了 {len(history)} 条消息了。\n\n有什么想聊的吗？"

    if "记住" in msg or "记得" in msg:
        return f"我记得我们之前的对话。\n\n我们已经聊了 {len(history)} 条消息。\n\n配置 API Key 后，我能真正理解你们的关系。"

    if "?" in msg or "？" in msg:
        return f"这是一个好问题。\n\n你问的是：「{message}」\n\n离线模式下我只能做简单回复。配置好 API Key 后，我能结合你们的关系背景给出有意义的回答。"

    return f"收到：「{message}」\n\n我们已经聊了 {len(history) + 1} 条消息了。\n\n*（离线模式 — 配置 API Key 后接入真实 AI）*"


# ---- 页面 ----

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(WEB_DIR / "chat.html")


# ---- 聊天 API（SSE 流式） ----

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式聊天接口"""
    person = req.person_name or req.conversation_id

    # 1. 保存用户消息
    user_event = create_event(
        type=EventType.CHAT,
        person=person,
        data={"role": "user", "content": req.message, "conversation_id": req.conversation_id},
    )
    _event_log.append(user_event)

    # 2. 获取历史消息
    history = get_conversation_history(req.conversation_id, limit=20)

    # 3. 构建 Context（Step 2 填充）
    context = await build_context(person, req.conversation_id)

    # 4. 流式生成回复
    async def generate():
        full_reply = ""
        async for chunk in stream_llm_response(req.message, context, history):
            full_reply += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

        # 5. 保存 AI 回复
        _event_log.append(create_event(
            type=EventType.CHAT,
            person=person,
            data={"role": "assistant", "content": full_reply, "conversation_id": req.conversation_id},
        ))

        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---- 会话 API ----

@app.get("/api/conversations")
async def list_conversations():
    """获取所有会话列表"""
    events = list(_event_log.iter_events())
    conv_map: dict[str, dict] = {}

    for e in events:
        if e.type == EventType.CHAT:
            cid = e.data.get("conversation_id", "default")
            if cid not in conv_map:
                conv_map[cid] = {
                    "id": cid,
                    "title": e.data.get("content", "")[:30],
                    "person_name": e.person,
                    "last_message": "",
                    "updated_at": "",
                    "message_count": 0,
                }
            conv_map[cid]["last_message"] = e.data.get("content", "")[:50]
            conv_map[cid]["updated_at"] = e.timestamp
            conv_map[cid]["message_count"] += 1

    return sorted(conv_map.values(), key=lambda x: x["updated_at"], reverse=True)


@app.post("/api/conversations")
async def create_conversation():
    """创建新会话"""
    cid = f"conv_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    return {"id": cid}


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = 100):
    """获取会话消息"""
    return get_conversation_history(conversation_id, limit)


# ---- 事件 API ----

@app.get("/api/events")
async def get_events(person: str = "", limit: int = 100):
    events = list(_event_log.iter_events())
    if person:
        events = [e for e in events if e.person == person]
    return [e.to_dict() for e in events[-limit:]]


# ---- 统计 API ----

@app.get("/api/stats")
async def stats():
    events = list(_event_log.iter_events())
    persons = set()
    for e in events:
        if e.person:
            persons.add(e.person)
    return {
        "total_events": len(events),
        "total_persons": len(persons),
        "persons": list(persons),
    }


# ---- 辅助函数 ----

def get_conversation_history(conversation_id: str, limit: int = 20) -> list[dict]:
    """获取会话历史消息"""
    events = list(_event_log.iter_events())
    messages = []
    for e in events:
        if e.type == EventType.CHAT and e.data.get("conversation_id") == conversation_id:
            messages.append({"role": e.data.get("role", "user"), "content": e.data.get("content", "")})
    return messages[-limit:]
