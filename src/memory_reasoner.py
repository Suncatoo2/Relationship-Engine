"""Memory Reasoner — "想" 的模块

职责：从 ContextObject 生成摘要和洞察。
  - summary: 人话描述"关于这个人，我知道什么"
  - highlights: 值得特别关注的信息
  - conflicts: 同 category 的历史冲突记录

不是 Projection，是 ContextObject 的增强层。
"""

from dataclasses import dataclass, field


@dataclass
class ReasonerOutput:
    """Reasoner 的输出"""
    summary: str = ""
    highlights: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "highlights": self.highlights,
            "conflicts": self.conflicts,
            "suggestions": self.suggestions,
        }


class MemoryReasoner:
    """记忆推理器 — 从 ContextObject 生成人话摘要"""

    def reason(self, ctx, insights: list | None = None) -> ReasonerOutput:
        """从 ContextObject 生成摘要和洞察

        Args:
            ctx: ContextObject
            insights: 可选，Cross-Projection Reasoner 产出的 Insight 列表。
                      如果提供，top 1-2 insights 会注入到 summary 中。

        Returns:
            ReasonerOutput
        """
        highlights: list[str] = []
        parts: list[str] = []

        name = ctx.identity.name if ctx.identity else "这个人"

        # 1. 记忆摘要
        if ctx.memory and ctx.memory.active_facts:
            categories = {}
            for f in ctx.memory.active_facts:
                categories.setdefault(f.category, []).append(f.content)

            for cat, contents in categories.items():
                label = self._category_label(cat)
                items = "、".join(contents[:3])
                parts.append(f"{label}：{items}")

        # 2. 关系洞察
        if ctx.relationship:
            stage = ctx.relationship.stage
            if stage and stage != "陌生人":
                chemistry = ctx.relationship.chemistry
                trend = ctx.relationship.trend
                parts.append(f"关系阶段：{stage}（好感度 {chemistry}，趋势 {trend}）")
                if ctx.relationship.last_contact_summary:
                    parts.append(f"最近联系：{ctx.relationship.last_contact_summary}")

        # 3. 时间洞察
        if ctx.time:
            if ctx.time.last_chat_label:
                parts.append(f"最后聊天：{ctx.time.last_chat_label}")
            if ctx.time.silence_label:
                highlights.append(f"沉默状态：{ctx.time.silence_label}")

        # 4. 情绪洞察
        if ctx.emotion:
            if ctx.emotion.dominant_emotion:
                parts.append(f"主导情绪：{ctx.emotion.dominant_emotion}")
            if ctx.emotion.alert:
                highlights.append(f"情绪警报：{ctx.emotion.alert}")

        # 5. 里程碑
        if ctx.relationship and ctx.relationship.milestones:
            for m in ctx.relationship.milestones[:2]:
                highlights.append(f"里程碑：{m}")

        # 6. 跨投影洞察（Step 3: Cross-Projection Reasoning）
        if insights:
            for insight in insights[:2]:  # top 2 insights only
                severity_icon = {"critical": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(
                    getattr(insight, "severity", "info") if hasattr(insight, "severity") else "info", "ℹ️"
                )
                highlights.append(f"{severity_icon} {insight.summary if hasattr(insight, 'summary') else str(insight)}")

        summary = f"关于{name}：" + "；".join(parts) if parts else ""

        return ReasonerOutput(
            summary=summary,
            highlights=highlights,
            metadata={"fact_count": ctx.memory.fact_count if ctx.memory else 0},
        )

    @staticmethod
    def _category_label(cat: str) -> str:
        labels = {
            "preference": "偏好",
            "general": "基本信息",
            "birthday": "生日",
            "hobby": "爱好",
            "story": "故事",
            "important": "重要事项",
            "secret": "秘密",
        }
        return labels.get(cat, cat)
