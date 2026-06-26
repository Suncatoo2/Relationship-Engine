"""Relationship Event OS — MCP Server

让任何 AI（DeepSeek、Qwen、GPT、Claude）通过 MCP 协议
调用关系管理能力。

Everything is Event. Everything else is Projection.
"""

import os
from mcp.server.fastmcp import FastMCP
from .event_types import create_event, EventType
from .event_log import EventLog
from .projections.context import ContextComposer
from .projections.prompt_builder import get_builder


# ---- 全局实例 ----

_data_dir = os.getenv("DATA_DIR", "data")
_event_log = EventLog(_data_dir)
_composer = ContextComposer()

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
    event = create_event(
        type=EventType.PERSON,
        person=name,
        data={"action": "create", "birthday": birthday, "nickname": nickname,
              "tags": tags or [], "notes": notes},
    )
    _event_log.append(event)
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
    event = create_event(
        type=EventType.FACT,
        person=person_name,
        data={"content": content, "category": category, "importance": importance},
    )
    _event_log.append(event)
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
    data = {"role": role, "content": content}
    if topics:
        data["topics"] = topics
    event = create_event(
        type=EventType.CHAT,
        person=person_name,
        data=data,
    )
    _event_log.append(event)
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
    event = create_event(
        type=EventType.EMOTION,
        person=person_name,
        data={"valence": valence, "arousal": arousal, "label": label, "context": context},
    )
    _event_log.append(event)
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
    data = {}
    if stage:
        data["stage"] = stage
    if chemistry_delta:
        data["delta"] = chemistry_delta
    if event_desc:
        data["event"] = event_desc
    event = create_event(
        type=EventType.RELATION,
        person=person_name,
        data=data,
    )
    _event_log.append(event)
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
    event = create_event(
        type=EventType.MILESTONE,
        person=person_name,
        data={"milestone_type": milestone_type, "description": description, "significance": significance},
    )
    _event_log.append(event)
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
    event = create_event(
        type=EventType.GROWTH,
        person=person_name,
        data={"title": title, "category": category, "description": description,
              "impact_level": impact_level, "date": date},
    )
    _event_log.append(event)
    return f"已记录成长: {title}"


# ============================================================
#  Read Tools — 读取视图
# ============================================================

@mcp.tool()
async def get_context(
    person_name: str,
    max_tokens: int = 6000,
    prompt_style: str = "default",
) -> str:
    """获取某人的完整 AI 上下文（最核心的读取接口）。

    综合所有 Projection，返回关于这个人 AI 最应该知道的一切。

    Args:
        person_name: 人名
        max_tokens: token 预算上限
        prompt_style: 输出格式（default/gpt/claude/deepseek）
    """
    composer = ContextComposer(budget_limit=max_tokens)
    snapshot = composer.compose(_event_log, person_name)

    builder = get_builder(prompt_style)
    return builder.build(snapshot)


@mcp.tool()
async def get_person(name: str) -> str:
    """获取某人的人物画像。

    Args:
        name: 人名
    """
    from .projections.person import PersonProjection
    proj = PersonProjection()
    profile = proj.project_one(list(_event_log.iter_events()), name)
    if not profile:
        return f"未找到 {name}"
    import json
    return json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def get_events(
    person_name: str = "",
    days: int = 30,
    event_type: str = "",
) -> str:
    """获取原始事件流。

    Args:
        person_name: 人名（可选，为空则返回所有）
        days: 最近多少天
        event_type: 事件类型过滤（可选）
    """
    import json
    events = list(_event_log.iter_events())
    if person_name:
        events = [e for e in events if e.person == person_name]
    if event_type:
        events = [e for e in events if e.type == event_type]
    events = events[-100:]  # 最多返回100条
    return json.dumps([e.to_dict() for e in events], ensure_ascii=False, indent=2)


@mcp.tool()
async def get_reminders() -> str:
    """获取所有提醒。"""
    from .projections.reminder import ReminderProjection
    proj = ReminderProjection()
    profile = proj.project(list(_event_log.iter_events()))
    import json
    return json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def search(keyword: str) -> str:
    """在所有事件中搜索关键词。

    Args:
        keyword: 搜索关键词
    """
    results = _event_log.search(keyword)
    import json
    return json.dumps([e.to_dict() for e in results[:20]], ensure_ascii=False, indent=2)


# ============================================================
#  Resources
# ============================================================

@mcp.resource("relationship://people")
def list_people() -> str:
    """获取所有人物列表"""
    from .projections.person import PersonProjection
    proj = PersonProjection()
    profiles = proj.project(list(_event_log.iter_events()))
    import json
    return json.dumps(
        {name: p.to_dict() for name, p in profiles.items()},
        ensure_ascii=False, indent=2,
    )


@mcp.resource("relationship://stats")
def get_stats() -> str:
    """获取系统统计摘要"""
    import json
    events = list(_event_log.iter_events())
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
