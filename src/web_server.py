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
from .memory_engine import MemoryEngine
from .provider import create_provider


# ---- 全局实例 ----

_data_dir = os.getenv("DATA_DIR", "data")
_event_log = EventLog(_data_dir)
_memory_engine = MemoryEngine(event_log=_event_log)
_llm_provider = create_provider()
_prompt_log_file = os.path.join(_data_dir, "prompts.jsonl")

print(f"Provider: {_llm_provider.name() if _llm_provider else '离线模式'}")

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

    调用 Memory Engine，自动读取记忆并生成 Context。
    Memory Engine 负责：读取 Event Log → Context Composer → Prompt Builder
    """
    result = _memory_engine.recall(person_name, conversation_id)
    return result.prompt_text


async def stream_llm_response(message: str, context: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """流式调用 LLM。

    优先使用真实 LLM Provider（DeepSeek/GPT/Claude）。
    没有配置时回退到离线模式。
    """
    if _llm_provider:
        system_prompt = build_system_prompt(context)
        messages = history + [{"role": "user", "content": message}]
        async for chunk in _llm_provider.stream_chat(system_prompt, messages):
            yield chunk
    else:
        reply = generate_offline_reply(message, history, context)
        for char in reply:
            yield char
            await asyncio.sleep(0.02)


def build_system_prompt(context: str) -> str:
    """构建 system prompt，注入 Memory Context"""
    base = (
        "你是 Relationship OS — 一个能够和人一起经历时间的 AI。\n"
        "你能记住用户的信息、关系、情绪和成长。\n"
        "根据以下关系上下文回复用户。自然地回复，像一个懂人心的朋友。\n"
        "不要提及你是 AI，不要说'根据上下文'。直接融入对话。\n"
        "如果上下文为空，说明这是第一次见面，自然地开始对话。\n"
    )
    if context:
        return f"{base}\n=== 关系记忆 ===\n{context}"
    return base


def generate_offline_reply(message: str, history: list[dict], context: str) -> str:
    """离线模式的智能回复（利用 Context）"""
    msg = message.strip().lower()

    if not history:
        if context:
            return f"你好！我记住了关于你的信息。\n\n我能感觉到我们之前有过交流。配置好 API Key 后，我能真正理解你、记住你，并随着时间陪伴你成长。"
        return f"你好！这是我们第一次聊天。\n\n你刚才说了：「{message}」\n\n我记住了。"

    if "你好" in msg or "hi" in msg or "hello" in msg:
        return f"你好！我们已经聊了 {len(history)} 条消息了。\n\n有什么想聊的吗？"

    if "记住" in msg or "记得" in msg:
        if context:
            return f"我记得我们的对话。\n\n我能感受到我们之间的关系。配置 API Key 后，我能结合这些记忆给出更有意义的回复。"
        return f"我记得我们之前的对话。\n\n我们已经聊了 {len(history)} 条消息。"

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

    # 1b. 自动提取事实（用户明确声明个人信息时保存为 fact）
    _auto_extract_facts(req.message, person)

    # 2. 获取历史消息
    history = get_conversation_history(req.conversation_id, limit=20)

    # 3. 构建 Context（通过 Memory Engine + Selector）
    memory_result = _memory_engine.recall(person, query=req.message, conversation_id=req.conversation_id)
    context = memory_result.prompt_text

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

        # 6. 保存 Prompt Log（完整 prompt 链路 + Provider Debug）
        import builtins
        provider_debug = getattr(builtins, '_provider_debug', {})
        save_prompt_log(
            conversation_id=req.conversation_id,
            person_name=person,
            user_message=req.message,
            context=context,
            system_prompt=f"你是 Relationship OS...\n\n{context}",
            assistant_reply=full_reply,
            debug_info=memory_result.debug_info,
            provider_debug=provider_debug,
        )

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


# ---- Debug API ----

@app.get("/api/debug/context/{person_name}")
async def debug_context(person_name: str):
    """获取某人的 Memory Debug 信息"""
    return {"summary": _memory_engine.get_debug_summary(person_name)}


@app.get("/api/debug/prompts")
async def debug_prompts(limit: int = 10):
    """获取最近的 Prompt Log"""
    if not os.path.exists(_prompt_log_file):
        return []
    with open(_prompt_log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line.strip()))
        except json.JSONDecodeError:
            pass
    return entries


# ---- 辅助函数 ----

def get_conversation_history(conversation_id: str, limit: int = 20) -> list[dict]:
    """获取会话历史消息"""
    events = list(_event_log.iter_events())
    messages = []
    for e in events:
        if e.type == EventType.CHAT and e.data.get("conversation_id") == conversation_id:
            messages.append({"role": e.data.get("role", "user"), "content": e.data.get("content", "")})
    return messages[-limit:]


def _auto_extract_facts(message: str, person: str):
    """自动提取事实：当用户明确声明个人信息时，保存为 fact 事件

    检测模式：
    - "记住：XXX" → 直接保存
    - "我叫XXX" "我是XXX" "我喜欢XXX" → 保存
    """
    import re
    msg = message.strip()

    # 模式1: "记住：XXX"
    if msg.startswith("记住：") or msg.startswith("记住:"):
        content = msg[3:].strip()
        if content:
            _event_log.append(create_event(
                type=EventType.FACT, person=person,
                data={"content": content, "category": "general", "importance": 8,
                      "source": "user_direct", "confidence": 0.95, "times_confirmed": 1},
            ))
            return

    # 模式2: "我是..." "我喜欢..." "我生日是..." "我养了..."
    patterns = [
        (r'^我是(.+)', 'general'),
        (r'^我(?:最)?喜欢(.+)', 'preference'),
        (r'^我(?:的)?生日是(.+)', 'birthday'),
        (r'^我养了(.+)', 'general'),
        (r'^我(?:是|学)(.+)专业', 'general'),
    ]
    for pat, cat in patterns:
        m = re.match(pat, msg)
        if m:
            content = m.group(1).strip().rstrip('。.!！')
            if content:
                _event_log.append(create_event(
                    type=EventType.FACT, person=person,
                    data={"content": msg, "category": cat, "importance": 8,
                          "source": "user_direct", "confidence": 0.95, "times_confirmed": 1},
                ))
            return


def save_prompt_log(
    conversation_id: str,
    person_name: str,
    user_message: str,
    context: str,
    system_prompt: str,
    assistant_reply: str,
    debug_info: dict,
    provider_debug: dict = None,
):
    """保存完整的 Prompt 链路（用于 Debug 和回放）"""
    os.makedirs(os.path.dirname(_prompt_log_file), exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "person_name": person_name,
        "user_message": user_message,
        "context": context,
        "system_prompt": system_prompt[:2000],  # 截断避免文件过大
        "assistant_reply": assistant_reply,
        "debug": debug_info,
        "provider": provider_debug or {},
    }
    with open(_prompt_log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
