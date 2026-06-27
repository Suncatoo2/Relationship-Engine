"""Memory Engine — 关系记忆引擎

Memory Engine 是 Relationship OS 的核心。
它不是数据库，而是"记忆的整理者"。

职责：
  - 从 Event Log 读取原始事件
  - 调用 Context Composer 生成 ContextSnapshot
  - 提供 Debug 信息
  - 未来：记忆整合、遗忘机制、长期摘要

不做的事：
  - 不存储数据（Event Log 负责）
  - 不决定发给 LLM 什么（Prompt Builder 负责）
  - 不做推理（调用方 AI 负责）
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .event_log import EventLog
from .projections.context import ContextComposer, ContextSnapshot
from .projections.prompt_builder import get_builder, BasePromptBuilder


@dataclass
class MemoryResult:
    """Memory Engine 的输出"""
    context_snapshot: ContextSnapshot
    prompt_text: str
    debug_info: dict
    metadata: dict = field(default_factory=dict)


class MemoryEngine:
    """关系记忆引擎

    依赖接口，不依赖实现：
      - EventLog 可替换
      - ContextComposer 可替换
      - PromptBuilder 可替换
    """

    def __init__(
        self,
        event_log: EventLog | None = None,
        composer: ContextComposer | None = None,
        builder_name: str = "default",
    ):
        self.event_log = event_log or EventLog("data")
        self.composer = composer or ContextComposer()
        self.builder = get_builder(builder_name)

    def recall(self, person_name: str, conversation_id: str = "") -> MemoryResult:
        """回忆：为某个人构建完整的记忆上下文

        这是 Memory Engine 的核心方法。
        输入：人名
        输出：ContextSnapshot + Prompt 文本 + Debug 信息
        """
        # 1. 读取所有事件
        events = list(self.event_log.iter_events())

        # 2. 调用 Context Composer 生成 ContextSnapshot
        snapshot = self.composer.compose(events, person_name)

        # 3. 调用 Prompt Builder 生成文本
        prompt_text = self.builder.build(snapshot)

        # 4. 构建 Debug 信息
        debug_info = self._build_debug_info(snapshot, events, person_name)

        # 5. 元数据
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "person_name": person_name,
            "conversation_id": conversation_id,
            "total_events": len(events),
            "prompt_length": len(prompt_text),
        }

        return MemoryResult(
            context_snapshot=snapshot,
            prompt_text=prompt_text,
            debug_info=debug_info,
            metadata=metadata,
        )

    def get_debug_summary(self, person_name: str) -> str:
        """获取人类可读的 Debug 摘要"""
        result = self.recall(person_name)
        lines = []
        lines.append(f"=== Memory Debug: {person_name} ===")
        lines.append(f"事件总数: {result.metadata['total_events']}")
        lines.append(f"Prompt 长度: {result.metadata['prompt_length']} 字符")
        lines.append("")

        snapshot = result.context_snapshot
        if snapshot.person:
            lines.append(f"人物: {snapshot.person.name}")
            if snapshot.person.birthday:
                lines.append(f"生日: {snapshot.person.birthday}")
            if snapshot.person.tags:
                lines.append(f"标签: {', '.join(snapshot.person.tags)}")
            if snapshot.person.facts:
                lines.append(f"记忆: {len(snapshot.person.facts)} 条")
                for f in snapshot.person.facts[:5]:
                    lines.append(f"  [{f.category}] {f.content}")

        if snapshot.relationship:
            lines.append(f"\n关系: {snapshot.relationship.stage}")
            lines.append(f"好感度: {snapshot.relationship.base_chemistry}")

        if snapshot.time:
            if snapshot.time.last_chat_label:
                lines.append(f"\n最后聊天: {snapshot.time.last_chat_label}")
            if snapshot.time.silence:
                lines.append(f"沉默状态: {snapshot.time.silence.label}")

        if snapshot.emotion:
            if snapshot.emotion.dominant_emotion:
                lines.append(f"\n主导情绪: {snapshot.emotion.dominant_emotion}")

        if snapshot.excluded:
            lines.append(f"\n因预算被排除: {', '.join(snapshot.excluded)}")

        lines.append(f"\n--- Prompt 内容 ---")
        lines.append(result.prompt_text[:500])

        return "\n".join(lines)

    def _build_debug_info(self, snapshot: ContextSnapshot, events: list, person_name: str) -> dict:
        """构建详细的 Debug 信息"""
        return {
            "person_name": person_name,
            "total_events": len(events),
            "snapshot_version": snapshot.version,
            "has_person": snapshot.person is not None,
            "has_relationship": snapshot.relationship is not None,
            "has_time": snapshot.time is not None,
            "has_emotion": snapshot.emotion is not None,
            "has_growth": snapshot.growth is not None,
            "has_conversation": snapshot.conversation is not None,
            "has_reminder": snapshot.reminder is not None,
            "excluded": snapshot.excluded,
            "token_used": snapshot.metadata.get("token_used", 0),
            "budget_limit": snapshot.metadata.get("budget_limit", 0),
            "prompt_preview": self.builder.build(snapshot)[:300],
        }
