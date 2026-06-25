"""AI 关系引擎核心 - 整合记忆、关系、对话，提供智能建议"""

import os
from openai import OpenAI
from ..memory import MemoryStore
from ..relationship import RelationshipTracker
from ..conversation import ConversationStore


SYSTEM_PROMPT = """你是一个顶级关系管理顾问 AI。你的工作是帮用户经营所有关系。

你的能力：
1. 记住每个人的信息（喜好、生日、习惯、你们的故事）
2. 追踪关系阶段和好感度
3. 在合适的时间给用户建议
4. 帮用户分析关系状况

你的风格：
- 像一个懂人心的老友，不说教
- 直接给实用建议，不废话
- 会用 emoji，轻松有趣
- 会主动提醒用户该做什么

当前关系数据：
{relationships}

当前人物记忆：
{memory}

对话上下文：
{conversation}
"""


class RelationshipEngine:
    """关系引擎 - 整合所有模块"""

    def __init__(self, data_dir: str = "data"):
        self.memory = MemoryStore(data_dir)
        self.tracker = RelationshipTracker(data_dir)
        self.conversation = ConversationStore(data_dir)
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None

    def _build_context(self, person_name: str = "") -> str:
        rels = self.tracker.list_all()
        rel_text = "\n".join(
            f"- {r.person_name}: {r.stage} | 好感度:{r.chemistry} | "
            f"上次联系:{r.last_contact[:10]}"
            for r in rels
        ) or "暂无关系数据"

        if person_name:
            facts = self.memory.recall(person_name)
            mem_text = "\n".join(
                f"- [{f.category}] {f.content}" for f in facts
            ) or f"关于 {person_name} 暂无记忆"
            conv_text = self.conversation.get_context(person_name, 10)
        else:
            mem_text = "请先指定要了解的人"
            conv_text = ""

        return SYSTEM_PROMPT.format(
            relationships=rel_text,
            memory=mem_text,
            conversation=conv_text,
        )

    def chat(self, user_message: str, person_name: str = "") -> str:
        """与 AI 对话"""
        if not self.client:
            return self._offline_response(user_message, person_name)

        self.conversation.add_message(person_name or "_general", "user", user_message)

        system = self._build_context(person_name)
        recent = self.conversation.get_recent(person_name or "_general", 10)
        messages = [{"role": "system", "content": system}]
        for msg in recent:
            messages.append({"role": msg.role, "content": msg.content})

        response = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.7, max_tokens=1000
        )
        reply = response.choices[0].message.content

        self.conversation.add_message(
            person_name or "_general", "assistant", reply
        )
        self._auto_extract(user_message, person_name)
        return reply

    def _offline_response(self, message: str, person_name: str) -> str:
        """离线模式 - 不调用 LLM，直接操作"""
        msg = message.strip()

        # 解析命令
        if msg.startswith("记住") or msg.startswith("记录"):
            if person_name:
                self.memory.remember(person_name, msg, category="general")
                return f"✅ 已记住关于 {person_name} 的信息：{msg}"
            return "请先指定要记住信息的人"

        if msg.startswith("查看") or msg.startswith("告诉我"):
            if person_name:
                facts = self.memory.recall(person_name)
                rel = self.tracker.get(person_name)
                lines = [f"📋 **{person_name}** 的信息："]
                if rel:
                    lines.append(f"  关系阶段: {rel.stage} | 好感度: {rel.chemistry}")
                for f in facts:
                    lines.append(f"  • [{f.category}] {f.content}")
                return "\n".join(lines) if facts else f"暂无 {person_name} 的记忆"

        # 默认提示
        return (
            "💡 离线模式可用命令：\n"
            "• `记住 [人名] [信息]` - 保存记忆\n"
            "• `查看 [人名]` - 查看某人信息\n"
            "• 配置 OPENAI_API_KEY 后可使用完整 AI 对话"
        )

    def _auto_extract(self, message: str, person_name: str):
        """从用户消息中自动提取关键信息"""
        if not person_name:
            return
        keywords = {
            "生日": "birthday", "喜欢": "preference",
            "讨厌": "preference", "爱好": "hobby",
            "工作": "general", "家住": "general",
        }
        for kw, cat in keywords.items():
            if kw in message:
                self.memory.remember(person_name, message, category=cat, importance=6)
                break

    def quick_add_person(self, name: str, rel_type: str = "朋友",
                         notes: str = "") -> dict:
        self.memory.add_person(name, relationship_type=rel_type, notes=notes)
        self.tracker.add_relationship(name)
        return {"status": "ok", "name": name, "type": rel_type}

    def quick_remember(self, person_name: str, content: str,
                       category: str = "general") -> dict:
        self.memory.remember(person_name, content, category=category)
        return {"status": "ok", "person": person_name, "content": content}

    def get_dashboard(self) -> dict:
        """获取仪表盘数据"""
        return {
            "people": [p.model_dump() for p in self.memory.list_people()],
            "relationships": [r.model_dump() for r in self.tracker.list_all()],
            "reminders": self.tracker.get_reminders(),
            "stats": {
                "memory": self.memory.stats(),
                "relationships": self.tracker.stats(),
            },
        }
