"""Relationship Event OS — MCP Server

让任何 AI（DeepSeek、Qwen、GPT、Claude）通过 MCP 协议
调用关系管理能力。

Everything is Event. Everything else is Projection.

Write: publish_interaction() → Pipeline
Read:  get_context() → Pipeline.recall() → ContextObject JSON
"""

import os
import json
from datetime import datetime, timezone, timedelta
from mcp.server.fastmcp import FastMCP
from .event_types import EventType
from .storage import JSONLStorage
from .dispatcher import ProjectionDispatcher
from .interaction_pipeline import InteractionPipeline, Interaction, FactInput, EmotionInput, RelationInput
from .projections.fact_state import FactProjection
from .projections.person import PersonProjection
from .projections.relationship import RelationshipProjection
from .projections.time_context import TimeContextProjection
from .projections.emotion import EmotionProjection
from .projections.growth import GrowthProjection


# ---- 全局实例（Pipeline 唯一入口）----

# 路径约定: data/{user_id}/events.jsonl
# user_id 由调用方决定，Engine 不关心如何认证（Principle #9）
_user_id = os.getenv("USER_ID", "local_default")
_data_dir = os.path.join(os.getenv("DATA_DIR", "data"), _user_id)
_storage = JSONLStorage(_data_dir)

_dispatcher = ProjectionDispatcher()
_dispatcher.register(FactProjection(),          event_types=["fact"])
_dispatcher.register(PersonProjection(),        event_types=["person", "fact"])
_dispatcher.register(RelationshipProjection(),  event_types=["relation", "chat", "milestone", "person"])
_dispatcher.register(TimeContextProjection(),   event_types=["chat", "person", "milestone"])
_dispatcher.register(EmotionProjection(),       event_types=["emotion"])
_dispatcher.register(GrowthProjection(),        event_types=["growth"])

_pipeline = InteractionPipeline(storage=_storage, dispatcher=_dispatcher)

mcp = FastMCP("RelationshipEventOS")


# ============================================================
#  Write Tools — 写入事件
# ============================================================

@mcp.tool()
async def add_person(
    name: str,
    birthday: str = "",
    nickname: str = "",
    tags: list[str] | None = None,
    notes: str = "",
) -> str:
    """添加一个新人物到系统。

    Args:
        name: 姓名（必填）
        birthday: 生日（YYYY-MM-DD）
        nickname: 昵称
        tags: 标签列表（如 ["口腔同学", "室友"]）
        notes: 备注
    """
    _pipeline.publish(Interaction(
        message=f"[添加人物] {name}",
        person=name,
        type="person",
        facts=[FactInput(content=f"生日:{birthday}", category="birthday")] if birthday else [],
    ))
    return f"已添加人物: {name}"


@mcp.tool()
async def remember(
    person_name: str,
    content: str,
    category: str = "general",
    importance: int = 5,
) -> str:
    """记住关于某人的一条信息/事实。

    Args:
        person_name: 人名
        content: 要记住的内容
        category: 分类（general/preference/birthday/hobby/story/important/secret）
        importance: 重要性 1-10
    """
    _pipeline.publish(Interaction(
        message=f"[记住] {content}",
        person=person_name,
        facts=[FactInput(content=content, category=category, importance=importance)],
    ))
    return f"已记住关于 {person_name} 的信息: {content}"


@mcp.tool()
async def add_chat(
    person_name: str,
    role: str,
    content: str,
    topics: list[str] | None = None,
) -> str:
    """记录一条聊天消息。

    Args:
        person_name: 对话对象
        role: 角色（user=用户说的, assistant=AI回复的）
        content: 消息内容
        topics: 话题标签（如 ["Python", "编程"]），用于话题统计
    """
    _pipeline.publish(Interaction(
        message=content,
        person=person_name,
        source=role,
    ))
    return f"已记录与 {person_name} 的对话"


@mcp.tool()
async def add_emotion(
    person_name: str,
    valence: float,
    label: str,
    arousal: float = 0.5,
    context: str = "",
) -> str:
    """记录一条情绪数据。

    Args:
        person_name: 人名
        valence: 情绪值 -1.0（负面）到 +1.0（正面）
        label: 情绪标签（开心/难过/焦虑/平静/兴奋/愤怒/压力）
        arousal: 唤醒度 0（平静）到 1（激动）
        context: 触发场景
    """
    _pipeline.publish(Interaction(
        message=f"[情绪] {label}",
        person=person_name,
        emotion=EmotionInput(valence=valence, arousal=arousal, label=label, context=context),
    ))
    return f"已记录 {person_name} 的情绪: {label}"


@mcp.tool()
async def update_relation(
    person_name: str,
    stage: str = "",
    chemistry_delta: int = 0,
    event_desc: str = "",
) -> str:
    """更新与某人的关系状态。

    Args:
        person_name: 人名
        stage: 新关系阶段（陌生人/认识/聊天/熟悉/朋友/重要的人/长期陪伴/暧昧/热恋/稳定/冷淡/分手）
        chemistry_delta: 好感度变化（正数升温，负数降温）
        event_desc: 触发事件描述
    """
    _pipeline.publish(Interaction(
        message=f"[关系] {event_desc or stage}",
        person=person_name,
        relation_change=RelationInput(stage=stage, delta=chemistry_delta, event=event_desc),
    ))
    return f"已更新 {person_name} 的关系"


@mcp.tool()
async def add_milestone(
    person_name: str,
    milestone_type: str,
    description: str,
    significance: int = 8,
) -> str:
    """记录一个关系里程碑。

    Args:
        person_name: 人名
        milestone_type: 里程碑类型（first_meet/first_chat/first_deep_talk/first_secret/first_fight/first_reconciliation/first_date/first_trip/first_collaboration/custom）
        description: 描述
        significance: 重要性 1-10
    """
    from .event_types import create_event
    event = create_event(
        type=EventType.MILESTONE,
        person=person_name,
        data={"milestone_type": milestone_type, "description": description, "significance": significance},
    )
    stored = _storage.append(event)
    _dispatcher.dispatch(stored)
    return f"已记录里程碑: {description}"


@mcp.tool()
async def add_growth(
    person_name: str,
    title: str,
    category: str,
    description: str = "",
    impact_level: int = 5,
    date: str = "",
) -> str:
    """记录一个成长节点。记录的是变化，不是简历。

    Args:
        person_name: 人名（通常是"我自己"）
        title: 标题（如"从遇到Bug就放弃到主动查文档"）
        category: 类型（skill/experience/milestone/achievement/realization）
        description: 描述
        impact_level: 影响程度 1-10
        date: 日期（YYYY-MM 或 YYYY-MM-DD）
    """
    from .event_types import create_event
    event = create_event(
        type=EventType.GROWTH,
        person=person_name,
        data={"title": title, "category": category, "description": description,
              "impact_level": impact_level, "date": date},
    )
    stored = _storage.append(event)
    _dispatcher.dispatch(stored)
    return f"已记录成长: {title}"


# ============================================================
#  Read Tools — 统一读取（全部经过 Pipeline）
# ============================================================

@mcp.tool()
async def get_context(
    person_name: str,
    max_tokens: int = 6000,
    prompt_style: str = "default",
) -> str:
    """获取某人的完整 AI 上下文（最核心的读取接口）。

    统一读取入口：Pipeline.recall() → ContextObject JSON。
    LLM 不再需要调用 get_person / get_events / get_reminders。

    Args:
        person_name: 人名
        max_tokens: token 预算上限
        prompt_style: 输出格式（default/gpt/claude/deepseek）
    """
    ctx = _pipeline.recall(person_name)
    return ctx.to_json()


@mcp.tool()
async def get_person(name: str) -> str:
    """获取某人的人物画像（兼容层，内部转发到 get_context）。

    Args:
        name: 人名
    """
    ctx = _pipeline.recall(name)
    d = ctx.to_dict()
    return json.dumps(d.get("identity", {}), ensure_ascii=False, indent=2)


@mcp.tool()
async def get_events(
    person_name: str = "",
    days: int = 30,
    event_type: str = "",
) -> str:
    """获取原始事件流（兼容层，内部读取 Storage）。

    Args:
        person_name: 人名（可选，为空则返回所有）
        days: 最近多少天
        event_type: 事件类型过滤（可选）
    """
    events = list(_storage.read_all())
    if person_name:
        events = [e for e in events if e.person == person_name]
    if event_type:
        events = [e for e in events if e.type == event_type]
    if days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = []
        for e in events:
            try:
                ts = datetime.fromisoformat(e.occurred_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    filtered.append(e)
            except (ValueError, TypeError):
                filtered.append(e)
        events = filtered
    events = events[-100:]
    return json.dumps([e.to_dict() for e in events], ensure_ascii=False, indent=2)


@mcp.tool()
async def get_reminders(person_name: str = "") -> str:
    """获取提醒（兼容层，内部转发到 get_context）。

    Args:
        person_name: 人名（可选）
    """
    ctx = _pipeline.recall(person_name) if person_name else None
    if ctx:
        d = ctx.to_dict()
        return json.dumps(d.get("time", {}), ensure_ascii=False, indent=2)
    return "{}"


@mcp.tool()
async def search(keyword: str) -> str:
    """在所有事件中搜索关键词（兼容层，内部读取 Storage）。

    Args:
        keyword: 搜索关键词
    """
    keyword_lower = keyword.lower()
    results = []
    for e in _storage.read_all():
        if keyword_lower in json.dumps(e.data, ensure_ascii=False).lower():
            results.append(e)
        elif keyword_lower in e.person.lower():
            results.append(e)
    return json.dumps([e.to_dict() for e in results[:20]], ensure_ascii=False, indent=2)


# ============================================================
#  Resources（兼容层，内部读取 Storage）
# ============================================================

@mcp.resource("relationship://people")
def list_people() -> str:
    """获取所有人物列表"""
    persons: dict[str, dict] = {}
    for e in _storage.read_all():
        if e.person and e.person not in persons:
            persons[e.person] = {"name": e.person, "first_seen": e.occurred_at}
    return json.dumps(persons, ensure_ascii=False, indent=2)


@mcp.resource("relationship://stats")
def get_stats() -> str:
    """获取系统统计摘要"""
    events = list(_storage.read_all())
    type_counts: dict[str, int] = {}
    persons: set[str] = set()
    for e in events:
        type_counts[e.type] = type_counts.get(e.type, 0) + 1
        if e.person:
            persons.add(e.person)
    return json.dumps({
        "total_events": len(events),
        "total_persons": len(persons),
        "by_type": type_counts,
    }, ensure_ascii=False, indent=2)
