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

from .event_types import EventType
from .interaction_pipeline import InteractionPipeline, Interaction, FactInput, EmotionInput, create_pipeline
from .memory_engine import MemoryEngine
from .prompt_adapter import get_adapter
from .provider import create_provider


# Snapshot 自动保存（每 write_ops 次写入后触发一次）
_write_counter = 0
SNAPSHOT_INTERVAL = 100  # 每 100 次写入自动保存一次快照


def _maybe_save_snapshot():
    """自动保存 Snapshot（写操作达到阈值时触发）"""
    global _write_counter
    _write_counter += 1
    if _write_counter >= SNAPSHOT_INTERVAL:
        try:
            _pipeline.save_snapshots()
        except Exception:
            pass  # Snapshot 失败不影响主流程
        _write_counter = 0

# 路径约定: data/{user_id}/events.jsonl
# user_id 由 API 层决定，Engine 不关心如何认证（Principle #9）
_user_id = os.getenv("USER_ID", "local_default")
_data_dir = os.getenv("DATA_DIR", "data")

# Pipeline — 唯一写入口，唯一读出口
# 通过 create_pipeline() 工厂统一配置（含全部 8 个 Projection）
_pipeline = create_pipeline(data_dir=_data_dir, user_id=_user_id)

_memory_engine = MemoryEngine(pipeline=_pipeline)
_llm_provider = create_provider()
# prompt log 放在与 events.jsonl 同目录（data/{user_id}/）
_prompt_log_file = os.path.join(os.path.dirname(_pipeline.storage._file_path), "prompts.jsonl")

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


# ---- Memory Engine 接口 ----

# build_context() 已移除 — 改用 Memory Engine.recall() 直接调用


async def stream_llm_response(message: str, context: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """流式调用 LLM。

    优先使用真实 LLM Provider（DeepSeek/GPT/Claude）。
    没有配置时回退到离线模式。
    """
    if _llm_provider:
        system_prompt = context  # PromptAdapter 已生成完整 Prompt
        messages = history + [{"role": "user", "content": message}]
        async for chunk in _llm_provider.stream_chat(system_prompt, messages):
            yield chunk
    else:
        reply = context  # 离线模式直接用 PromptAdapter 输出
        for char in reply:
            yield char
            await asyncio.sleep(0.02)


# build_system_prompt() — removed (replaced by PromptAdapter)
# generate_offline_reply() — removed (replaced by PromptAdapter)


# ---- 页面 ----

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(WEB_DIR / "chat.html")


# ---- 聊天 API（SSE 流式） ----

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式聊天接口"""
    person = req.person_name or req.conversation_id

    # 1. 本地模式提取 facts（纯规则，不走 LLM）
    extracted = _extract_local_facts(req.message)

    # 2. 一次性 publish：chat + facts → Pipeline → Storage → Dispatcher
    _pipeline.publish(Interaction(
        message=req.message,
        person=person,
        facts=extracted,
        conversation_id=req.conversation_id,
    ))
    _maybe_save_snapshot()

    # 3. 获取历史消息
    history = get_conversation_history(req.conversation_id, limit=20)

    # 4. 构建 Context（通过 Memory Engine.recall → Pipeline）
    memory_result = _memory_engine.recall(person, query=req.message, conversation_id=req.conversation_id)
    context = memory_result.prompt_text

    # 5. 流式生成回复
    async def generate():
        full_reply = ""
        async for chunk in stream_llm_response(req.message, context, history):
            full_reply += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

        # 6. 保存 AI 回复（走 Pipeline，保持唯一写入口）
        _pipeline.publish(Interaction(
            message=full_reply,
            person=person,
            conversation_id=req.conversation_id,
            source="assistant",
        ))
        _maybe_save_snapshot()

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
    events = list(_pipeline.storage.read_all())
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
            conv_map[cid]["updated_at"] = e.occurred_at
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
    events = list(_pipeline.storage.read_all())
    if person:
        events = [e for e in events if e.person == person]
    return [e.to_dict() for e in events[-limit:]]


# ---- 统计 API ----

@app.get("/api/stats")
async def stats():
    events = list(_pipeline.storage.read_all())
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


@app.get("/api/debug/explain")
async def debug_explain(person: str, query: str = ""):
    """解释 AI 为什么这样回答——展示使用了哪些记忆"""
    # 使用 Pipeline.recall() 新架构替代旧 MemorySelector
    ctx = _pipeline.recall(person).context
    facts_used = []
    if ctx.memory and ctx.memory.active_facts:
        for f in ctx.memory.active_facts:
            facts_used.append({
                "content": f.content, "category": f.category,
                "confidence": f.confidence, "status": f.status,
            })
    return {
        "query": query,
        "total_facts": ctx.memory.fact_count if ctx.memory else 0,
        "selected_facts": len(facts_used),
        "facts_used": facts_used,
    }


# ---- 辅助函数 ----

def get_conversation_history(conversation_id: str, limit: int = 20) -> list[dict]:
    """获取会话历史消息"""
    events = list(_pipeline.storage.read_all())
    messages = []
    for e in events:
        if e.type == EventType.CHAT and e.data.get("conversation_id") == conversation_id:
            messages.append({"role": e.data.get("role", "user"), "content": e.data.get("content", "")})
    return messages[-limit:]


def _extract_local_facts(message: str) -> list[FactInput]:
    """本地模式提取事实（纯规则，不走 LLM）

    返回 FactInput 列表，由 Pipeline.publish() 负责写入 Event。
    FactProjection.apply() 负责同 category 去重（deprecation）。
    """
    import re
    msg = message.strip()

    if msg.endswith(("？", "?")):
        return []
    if any(msg.startswith(q) for q in ("什么", "怎么", "为什么", "谁", "哪", "请问")):
        return []

    facts: list[FactInput] = []

    def _save(content: str, category: str, source: str = "user_direct", confidence: float = 0.95):
        facts.append(FactInput(
            content=content,
            category=category,
            importance=8,
            confidence=confidence,
        ))

    if msg.startswith("记住：") or msg.startswith("记住:"):
        content = msg[3:].strip()
        if content:
            _save(content, "general")
        return facts

    patterns = [
        (r'^我是(.+)', 'general'),
        (r'^我(?:最)?喜欢(.+)', 'preference'),
        (r'^我(?:的)?生日是(.+)', 'birthday'),
        (r'^我养了(.+)', 'general'),
        (r'^(.+)是我的最爱', 'preference'),
    ]
    for pat, cat in patterns:
        m = re.match(pat, msg)
        if m:
            captured = m.group(1).strip().rstrip('。.!！？?')
            if captured and len(captured) > 1 and not any(q in captured for q in ('什么', '怎么', '为什么', '谁', '哪')):
                _save(captured, cat)
            return facts

    return facts


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
