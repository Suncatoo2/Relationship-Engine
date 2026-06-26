"""Prompt Builder — 把 ContextSnapshot 变成 LLM Prompt

不同 LLM 有不同的偏好格式：
  - Claude: XML 标签
  - GPT: Markdown
  - Gemini: JSON
  - DeepSeek: 简洁纯文本

Prompt Builder 只做格式转换，不做计算。
"""

from abc import ABC, abstractmethod
from .context import ContextSnapshot


class BasePromptBuilder(ABC):
    """Prompt Builder 基类"""

    def build(self, snapshot: ContextSnapshot, style: str = "default") -> str:
        """把 ContextSnapshot 变成 Prompt 文本"""
        sections = []

        # 人物信息
        if snapshot.person:
            sections.append(self._format_person(snapshot.person))

        # 关系状态
        if snapshot.relationship:
            sections.append(self._format_relationship(snapshot.relationship))

        # 时间感知
        if snapshot.time:
            sections.append(self._format_time(snapshot.time))

        # 情绪
        if snapshot.emotion:
            sections.append(self._format_emotion(snapshot.emotion))

        # 成长
        if snapshot.growth:
            sections.append(self._format_growth(snapshot.growth))

        # 对话
        if snapshot.conversation:
            sections.append(self._format_conversation(snapshot.conversation))

        # 提醒
        if snapshot.reminder:
            sections.append(self._format_reminder(snapshot.reminder))

        # 预算信息
        if snapshot.excluded:
            sections.append(self._format_excluded(snapshot.excluded))

        return self._join_sections(sections)

    @abstractmethod
    def _format_person(self, person) -> str: ...

    @abstractmethod
    def _format_relationship(self, rel) -> str: ...

    @abstractmethod
    def _format_time(self, time) -> str: ...

    @abstractmethod
    def _format_emotion(self, emotion) -> str: ...

    @abstractmethod
    def _format_growth(self, growth) -> str: ...

    @abstractmethod
    def _format_conversation(self, conv) -> str: ...

    @abstractmethod
    def _format_reminder(self, reminder) -> str: ...

    @abstractmethod
    def _format_excluded(self, excluded: list[str]) -> str: ...

    @abstractmethod
    def _join_sections(self, sections: list[str]) -> str: ...


class DefaultBuilder(BasePromptBuilder):
    """默认格式（纯文本，通用）"""

    def _format_person(self, p) -> str:
        lines = [f"[人物] {p.name}"]
        if p.nickname:
            lines[0] += f"（{p.nickname}）"
        if p.birthday:
            lines.append(f"  生日: {p.birthday}")
        if p.tags:
            lines.append(f"  标签: {', '.join(p.tags)}")
        if p.facts:
            lines.append(f"  记忆({len(p.facts)}条):")
            for f in p.facts[:5]:
                lines.append(f"    [{f.category}] {f.content}")
        return "\n".join(lines)

    def _format_relationship(self, r) -> str:
        lines = [f"[关系] {r.stage} | 好感度: {r.base_chemistry}"]
        if r.decay_chemistry != r.base_chemistry:
            lines[0] += f"（衰减后: {r.decay_chemistry}）"
        lines.append(f"  趋势: {r.trend}")
        if r.milestones:
            lines.append(f"  里程碑: {len(r.milestones)}个")
        return "\n".join(lines)

    def _format_time(self, t) -> str:
        lines = ["[时间]"]
        if t.last_chat_label:
            lines.append(f"  最后聊天: {t.last_chat_label}")
        if t.time_scale:
            lines.append(f"  时间尺度: {t.time_scale}")
        if t.silence:
            lines.append(f"  沉默: {t.silence.label}")
        if t.density_7d:
            lines.append(f"  7天密度: {t.density_7d.label}")
        return "\n".join(lines)

    def _format_emotion(self, e) -> str:
        lines = [f"[情绪] 趋势: {e.trend.value}"]
        if e.current:
            lines.append(f"  当前: {e.current.label}")
        if e.dominant_emotion:
            lines.append(f"  主导: {e.dominant_emotion}")
        if e.alerts:
            for a in e.alerts:
                lines.append(f"  ⚠️ {a.message}")
        return "\n".join(lines)

    def _format_growth(self, g) -> str:
        lines = [f"[成长] {g.total_nodes}个节点"]
        if g.milestones:
            lines.append(f"  里程碑: {len(g.milestones)}个")
            for m in g.milestones[:3]:
                lines.append(f"    {m.title} ({m.date})")
        return "\n".join(lines)

    def _format_conversation(self, c) -> str:
        lines = [f"[对话] 密度: {c.density_label}"]
        if c.top_topics:
            lines.append(f"  话题: {', '.join(c.top_topics)}")
        if c.all_time:
            lines.append(f"  总消息: {c.all_time.message_count}")
        return "\n".join(lines)

    def _format_reminder(self, r) -> str:
        if not r.items:
            return "[提醒] 无"
        lines = [f"[提醒] {r.pending}条待处理"]
        for item in r.items[:5]:
            lines.append(f"  {item.urgency.value}: {item.message}")
        return "\n".join(lines)

    def _format_excluded(self, excluded: list[str]) -> str:
        return f"[注意] 以下信息因预算限制被省略: {', '.join(excluded)}"

    def _join_sections(self, sections: list[str]) -> str:
        return "\n\n".join(sections)


class GPTBuilder(DefaultBuilder):
    """GPT 偏好：Markdown 格式"""

    def _format_person(self, p) -> str:
        lines = [f"## 人物: {p.name}"]
        if p.birthday:
            lines.append(f"- 生日: {p.birthday}")
        if p.tags:
            lines.append(f"- 标签: {', '.join(p.tags)}")
        if p.facts:
            lines.append(f"- 记忆({len(p.facts)}条):")
            for f in p.facts[:5]:
                lines.append(f"  - [{f.category}] {f.content}")
        return "\n".join(lines)

    def _join_sections(self, sections: list[str]) -> str:
        return "\n\n---\n\n".join(sections)


class ClaudeBuilder(DefaultBuilder):
    """Claude 偏好：XML 标签格式"""

    def _format_person(self, p) -> str:
        lines = [f"<person name=\"{p.name}\">"]
        if p.birthday:
            lines.append(f"  <birthday>{p.birthday}</birthday>")
        if p.tags:
            lines.append(f"  <tags>{', '.join(p.tags)}</tags>")
        if p.facts:
            for f in p.facts[:5]:
                lines.append(f"  <fact category=\"{f.category}\">{f.content}</fact>")
        lines.append("</person>")
        return "\n".join(lines)

    def _join_sections(self, sections: list[str]) -> str:
        return f"<relationship_context>\n{chr(10).join(sections)}\n</relationship_context>"


class DeepSeekBuilder(DefaultBuilder):
    """DeepSeek 偏好：简洁纯文本"""

    def _format_person(self, p) -> str:
        parts = [p.name]
        if p.birthday:
            parts.append(f"生日{p.birthday}")
        if p.tags:
            parts.append("/".join(p.tags))
        if p.facts:
            parts.append("; ".join(f.content for f in p.facts[:3]))
        return " | ".join(parts)

    def _format_relationship(self, r) -> str:
        return f"{r.stage} {r.base_chemistry}分 {r.trend}"

    def _format_time(self, t) -> str:
        parts = []
        if t.last_chat_label:
            parts.append(t.last_chat_label)
        if t.silence:
            parts.append(t.silence.label)
        return " | ".join(parts) if parts else ""

    def _join_sections(self, sections: list[str]) -> str:
        return "\n".join(s for s in sections if s)


# ---- 工厂 ----

BUILDERS = {
    "default": DefaultBuilder,
    "gpt": GPTBuilder,
    "claude": ClaudeBuilder,
    "deepseek": DeepSeekBuilder,
}


def get_builder(name: str = "default") -> BasePromptBuilder:
    cls = BUILDERS.get(name, DefaultBuilder)
    return cls()
