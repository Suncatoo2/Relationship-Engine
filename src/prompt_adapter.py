"""PromptAdapter — Output Compiler（输出编译层）

ContextObject → Prompt 文本 → 不同 LLM

职责（只翻译，不推理）:
  - 根据关系深度调整语气
  - 注入 Suggestions
  - 组织 Context 结构
  - 适配 LLM 格式（Claude XML / GPT Markdown / DeepSeek 纯文本）

PromptAdapter 像「翻译官」，不是「思考者」。
"""

from abc import ABC, abstractmethod
from .protocol import ContextObject


# ============================================================
#  抽象接口 — Deep Module: tiny interface, deep implementation
# ============================================================

class PromptAdapter(ABC):
    """Prompt Adapter 基类

    Interface: build(ctx: ContextObject) -> str
    每个子类只实现这一个方法。
    """

    @abstractmethod
    def build(self, ctx: ContextObject) -> str:
        """把 ContextObject 翻译成 LLM 可消费的 Prompt 文本

        Args:
            ctx: Pipeline.recall() 返回的 ContextObject

        Returns:
            Prompt 文本（直接注入 system prompt）
        """
        ...

    def _tone_for_stage(self, stage: str) -> str:
        """根据关系阶段返回语气描述（确定性映射）"""
        tones = {
            "陌生人": "用敬语，保持礼貌距离",
            "认识":   "友好但不亲密",
            "聊天":   "自然随和",
            "熟悉":   "轻松自然",
            "朋友":   "真诚、关心",
            "重要的人": "温暖、深度关心",
            "长期陪伴": "默契、不需要客套",
            "暧昧":   "温柔、略带亲昵",
            "热恋":   "亲密、深情",
            "稳定":   "默契、舒适",
            "冷淡":   "温和但不强求",
        }
        return tones.get(stage, "自然友好")

    def _format_suggestions(self, ctx: ContextObject) -> str:
        """格式化 suggestions（如果有的话）"""
        suggestions = getattr(ctx, "suggestions", None)
        if not suggestions:
            return ""
        lines = ["[主动建议]"]
        for s in suggestions:
            lines.append(f"- {s}")
        return "\n".join(lines)


# ============================================================
#  Claude Adapter — XML 标签格式
# ============================================================

class ClaudeAdapter(PromptAdapter):
    """Claude 偏好 XML 标签格式"""

    def build(self, ctx: ContextObject) -> str:
        d = ctx.to_dict()
        sections = []

        # Identity
        name = d["identity"]["name"]
        sections.append(f"<identity>{name}</identity>")

        # Memory
        memory = d["memory"]
        if memory["memory_summary"]:
            sections.append(f"<memory_summary>{memory['memory_summary']}</memory_summary>")
        if memory["active_facts"]:
            facts = "\n".join(f"  - [{f['category']}] {f['content']}" for f in memory["active_facts"])
            sections.append(f"<facts>\n{facts}\n</facts>")

        # Relationship
        rel = d["relationship"]
        if rel["stage"] != "陌生人":
            sections.append(f"<relationship stage=\"{rel['stage']}\" chemistry=\"{rel['chemistry']}\" trend=\"{rel['trend']}\" />")

        # Time
        time = d["time"]
        if time["last_chat_label"]:
            sections.append(f"<time last_chat=\"{time['last_chat_label']}\" silence=\"{time['silence_label']}\" />")

        # Emotion
        emotion = d.get("emotion")
        if emotion:
            sections.append(f"<emotion dominant=\"{emotion['dominant_emotion']}\" trend=\"{emotion['trend']}\" />")

        # Goals
        goals = d.get("goals")
        if goals and goals.get("active_goals"):
            goal_lines = "\n".join(f"  - {g['title']}" for g in goals["active_goals"])
            sections.append(f"<goals>\n{goal_lines}\n</goals>")

        # Suggestions
        suggestions_text = self._format_suggestions(ctx)
        if suggestions_text:
            sections.append(f"<suggestions>\n{suggestions_text}\n</suggestions>")

        # Tone instruction
        tone = self._tone_for_stage(rel["stage"])
        sections.append(f"<tone>{tone}</tone>")

        return "\n\n".join(sections)


# ============================================================
#  GPT Adapter — Markdown 格式
# ============================================================

class GPTAdapter(PromptAdapter):
    """GPT 偏好 Markdown 格式"""

    def build(self, ctx: ContextObject) -> str:
        d = ctx.to_dict()
        sections = []

        name = d["identity"]["name"]
        sections.append(f"# 关于 {name}")

        memory = d["memory"]
        if memory["memory_summary"]:
            sections.append(f"## 记忆\n{memory['memory_summary']}")
        if memory["active_facts"]:
            facts = "\n".join(f"- [{f['category']}] {f['content']}" for f in memory["active_facts"])
            sections.append(f"## 事实\n{facts}")

        rel = d["relationship"]
        if rel["stage"] != "陌生人":
            sections.append(f"## 关系\n阶段: {rel['stage']} | 好感度: {rel['chemistry']} | 趋势: {rel['trend']}")
            if rel["last_contact_summary"]:
                sections.append(f"最近联系: {rel['last_contact_summary']}")

        time = d["time"]
        if time["last_chat_label"]:
            sections.append(f"## 时间\n最后聊天: {time['last_chat_label']} | 沉默: {time['silence_label']}")

        emotion = d.get("emotion")
        if emotion:
            sections.append(f"## 情绪\n主导: {emotion['dominant_emotion']} | 趋势: {emotion['trend']}")

        goals = d.get("goals")
        if goals and goals.get("active_goals"):
            goal_lines = "\n".join(f"- {g['title']}" for g in goals["active_goals"])
            sections.append(f"## 目标\n{goal_lines}")

        suggestions_text = self._format_suggestions(ctx)
        if suggestions_text:
            sections.append(f"## 建议\n{suggestions_text}")

        tone = self._tone_for_stage(rel["stage"])
        sections.append(f"---\n*语气: {tone}*")

        return "\n\n".join(sections)


# ============================================================
#  DeepSeek Adapter — 简洁纯文本
# ============================================================

class DeepSeekAdapter(PromptAdapter):
    """DeepSeek 偏好简洁纯文本"""

    def build(self, ctx: ContextObject) -> str:
        d = ctx.to_dict()
        lines = []

        name = d["identity"]["name"]
        lines.append(f"【{name}】")

        memory = d["memory"]
        if memory["memory_summary"]:
            lines.append(memory["memory_summary"])

        rel = d["relationship"]
        if rel["stage"] != "陌生人":
            lines.append(f"关系: {rel['stage']} ({rel['chemistry']}分) {rel['trend']}")

        time = d["time"]
        if time["last_chat_label"]:
            lines.append(f"联系: {time['last_chat_label']}，{time['silence_label']}")

        emotion = d.get("emotion")
        if emotion:
            lines.append(f"情绪: {emotion['dominant_emotion']} ({emotion['trend']})")

        goals = d.get("goals")
        if goals and goals.get("active_goals"):
            goal_text = "、".join(g["title"] for g in goals["active_goals"])
            lines.append(f"目标: {goal_text}")

        suggestions = getattr(ctx, "suggestions", None)
        if suggestions:
            lines.append("建议: " + "；".join(suggestions))

        tone = self._tone_for_stage(rel["stage"])
        lines.append(f"语气: {tone}")

        return "\n".join(lines)


# ============================================================
#  工厂函数
# ============================================================

_ADAPTERS = {
    "claude": ClaudeAdapter,
    "gpt": GPTAdapter,
    "deepseek": DeepSeekAdapter,
    "default": DeepSeekAdapter,
}


def get_adapter(name: str = "default") -> PromptAdapter:
    """获取 Prompt Adapter 实例

    Args:
        name: "claude" / "gpt" / "deepseek" / "default"

    Returns:
        PromptAdapter 实例
    """
    cls = _ADAPTERS.get(name, DeepSeekAdapter)
    return cls()
