"""Relationship Engine - MCP Server

让任何 AI（DeepSeek、Qwen、GPT、Claude）通过 MCP 协议
调用关系管理能力。不绑定任何 LLM，只提供 Tools 和 Resources。
"""

import os
import json
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from .memory import MemoryStore
from .relationship import RelationshipTracker
from .conversation import ConversationStore


# ---- Lifespan: 初始化数据存储 ----

@asynccontextmanager
async def lifespan(server):
    data_dir = os.getenv("DATA_DIR", "data")
    yield {
        "memory": MemoryStore(data_dir),
        "tracker": RelationshipTracker(data_dir),
        "conversation": ConversationStore(data_dir),
    }


mcp = FastMCP("RelationshipEngine", lifespan=lifespan)


# ============================================================
#  Tools — 任何 AI 都可以调用的 7 个工具
# ============================================================

@mcp.tool()
async def add_person(
    name: str,
    relationship_type: str = "朋友",
    nickname: str = "",
    birthday: str = "",
    notes: str = "",
) -> str:
    """添加一个新人物到关系库。

    Args:
        name: 姓名（必填）
        relationship_type: 关系类型（朋友/暧昧/恋人/前任/同事/家人）
        nickname: 昵称
        birthday: 生日（格式 YYYY-MM-DD）
        notes: 备注
    """
    from mcp.server.fastmcp import Context
    import inspect
    ctx = inspect.currentframe().f_locals.get("ctx")

    store = _get_memory()
    tracker = _get_tracker()
    store.add_person(name, relationship_type=relationship_type,
                     nickname=nickname, birthday=birthday, notes=notes)
    tracker.add_relationship(name)
    return f"✅ 已添加: {name}（{relationship_type}）"


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
        content: 要记住的内容（喜好、习惯、故事等）
        category: 分类（general/preference/birthday/hobby/story/important）
        importance: 重要性 1-10（越高越重要）
    """
    store = _get_memory()
    if not store.get_person(person_name):
        store.add_person(person_name)
        _get_tracker().add_relationship(person_name)
    fact = store.remember(person_name, content, category=category, importance=importance)
    return f"✅ 已记住关于 {person_name} 的信息: {content}"


@mcp.tool()
async def add_chat_message(
    person_name: str,
    role: str,
    content: str,
) -> str:
    """记录一条聊天消息到对话历史。

    Args:
        person_name: 对话对象的名字
        role: 角色（user=用户说的, assistant=AI回复的）
        content: 消息内容
    """
    conv = _get_conversation()
    conv.start_session(person_name)
    conv.add_message(person_name, role, content)
    _get_tracker().touch(person_name)
    return f"✅ 已记录与 {person_name} 的对话消息"


@mcp.tool()
async def update_relationship(
    person_name: str,
    stage: str = "",
    chemistry_delta: int = 0,
    event: str = "",
    event_type: str = "general",
) -> str:
    """更新与某人的关系状态。

    Args:
        person_name: 人名
        stage: 新关系阶段（认识/朋友/暧昧/热恋/稳定/冷淡/分手）
        chemistry_delta: 好感度变化（正数升温，负数降温）
        event: 发生的事件描述
        event_type: 事件类型（general/date/gift/argument/milestone/sweet）
    """
    tracker = _get_tracker()
    results = []
    if stage:
        rel = tracker.update_stage(person_name, stage)
        if rel:
            results.append(f"关系阶段更新为: {stage}")
    if chemistry_delta:
        rel = tracker.update_chemistry(person_name, chemistry_delta)
        if rel:
            results.append(f"好感度变化: {chemistry_delta:+d} → {rel.chemistry}")
    if event:
        evt = tracker.add_event(person_name, event, event_type=event_type,
                                emotional_impact=chemistry_delta)
        if evt:
            results.append(f"已记录事件: {event}")
    if not results:
        return f"⚠️ 未找到 {person_name}，请先用 add_person 添加"
    return f"✅ {person_name}: " + "；".join(results)


@mcp.tool()
async def query_person(name: str) -> str:
    """查询某人的完整信息（画像 + 关系 + 记忆 + 近期对话）。

    Args:
        name: 人名
    """
    store = _get_memory()
    tracker = _get_tracker()
    conv = _get_conversation()

    profile = store.get_person(name)
    if not profile:
        return f"⚠️ 未找到 {name} 的记录"

    rel = tracker.get(name)
    facts = store.recall(name)
    recent = conv.get_recent(name, 10)

    lines = [f"👤 **{name}**"]
    if profile.nickname:
        lines[0] += f"（{profile.nickname}）"
    lines.append(f"关系类型: {profile.relationship_type}")
    if profile.birthday:
        lines.append(f"生日: {profile.birthday}")
    if profile.notes:
        lines.append(f"备注: {profile.notes}")

    if rel:
        lines.append(f"\n📊 **关系状态**")
        lines.append(f"阶段: {rel.stage} | 好感度: {rel.chemistry}%")
        lines.append(f"上次联系: {rel.last_contact[:10]}")
        if rel.milestones:
            lines.append(f"里程碑: {'; '.join(rel.milestones[-3:])}")

    if facts:
        lines.append(f"\n🧠 **记忆**（{len(facts)} 条）")
        for f in facts[:10]:
            lines.append(f"  [{f.category}] {f.content}")

    if recent:
        lines.append(f"\n💬 **近期对话**（{len(recent)} 条）")
        for msg in recent[-5:]:
            role = "用户" if msg.role == "user" else "AI"
            lines.append(f"  [{role}] {msg.content[:100]}")

    return "\n".join(lines)


@mcp.tool()
async def get_reminders() -> str:
    """获取所有提醒：太久没联系的人、即将到来的生日等。"""
    tracker = _get_tracker()
    store = _get_memory()

    reminders = tracker.get_reminders()

    # 生日提醒
    from datetime import datetime
    now = datetime.now()
    for profile in store.list_people():
        if profile.birthday:
            try:
                bd = datetime.strptime(profile.birthday, "%Y-%m-%d")
                days_until = (bd.replace(year=now.year) - now).days
                if days_until < 0:
                    days_until = (bd.replace(year=now.year + 1) - now).days
                if 0 <= days_until <= 7:
                    reminders.append({
                        "person": profile.name,
                        "type": "birthday",
                        "message": f"🎂 {profile.name} 的生日还有 {days_until} 天！准备一下吧",
                        "urgency": "high" if days_until <= 3 else "medium",
                    })
            except ValueError:
                pass

    if not reminders:
        return "✅ 一切正常，暂无提醒"

    lines = ["⏰ **提醒事项**\n"]
    for r in sorted(reminders, key=lambda x: 0 if x.get("urgency") == "high" else 1):
        icon = "🔴" if r.get("urgency") == "high" else "🟡"
        lines.append(f"{icon} {r['message']}")
    return "\n".join(lines)


@mcp.tool()
async def search_memory(keyword: str) -> str:
    """在所有人物记忆中搜索关键词。

    Args:
        keyword: 搜索关键词
    """
    store = _get_memory()
    results = store.search(keyword)
    if not results:
        return f"未找到包含「{keyword}」的记忆"

    lines = [f"🔍 搜索「{keyword}」找到 {len(results)} 条结果:\n"]
    for person_name, fact in results:
        lines.append(f"  👤 {person_name} [{fact.category}] {fact.content}")
    return "\n".join(lines)


# ============================================================
#  Resources — AI 可读取的数据端点
# ============================================================

@mcp.resource("relationship://people")
def list_people() -> str:
    """获取所有人物列表"""
    store = _get_memory()
    tracker = _get_tracker()
    people = store.list_people()
    if not people:
        return json.dumps({"people": [], "total": 0}, ensure_ascii=False)

    result = []
    for p in people:
        rel = tracker.get(p.name)
        result.append({
            "name": p.name,
            "nickname": p.nickname,
            "relationship_type": p.relationship_type,
            "birthday": p.birthday,
            "stage": rel.stage if rel else "未知",
            "chemistry": rel.chemistry if rel else 0,
            "facts_count": len(p.facts),
            "last_contact": rel.last_contact[:10] if rel else "",
        })
    return json.dumps({"people": result, "total": len(result)},
                      ensure_ascii=False, indent=2)


@mcp.resource("relationship://stats")
def get_stats() -> str:
    """获取关系统计摘要"""
    store = _get_memory()
    tracker = _get_tracker()
    conv = _get_conversation()
    return json.dumps({
        "memory": store.stats(),
        "relationships": tracker.stats(),
    }, ensure_ascii=False, indent=2)


# ============================================================
#  内部辅助
# ============================================================

def _get_memory() -> MemoryStore:
    from mcp.server.fastmcp import Context
    import inspect
    # 从 lifespan context 获取，如果不在 MCP 环境则创建默认实例
    try:
        return _default_instances["memory"]
    except (NameError, KeyError):
        pass
    return _get_default()["memory"]


def _get_tracker() -> RelationshipTracker:
    try:
        return _default_instances["tracker"]
    except (NameError, KeyError):
        pass
    return _get_default()["tracker"]


def _get_conversation() -> ConversationStore:
    try:
        return _default_instances["conversation"]
    except (NameError, KeyError):
        pass
    return _get_default()["conversation"]


_default_instances = {}


def _get_default():
    if not _default_instances:
        data_dir = os.getenv("DATA_DIR", "data")
        _default_instances["memory"] = MemoryStore(data_dir)
        _default_instances["tracker"] = RelationshipTracker(data_dir)
        _default_instances["conversation"] = ConversationStore(data_dir)
    return _default_instances
