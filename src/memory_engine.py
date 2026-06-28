"""Memory Engine — 关系记忆引擎

Memory Engine 是 Relationship OS 的核心。
它不是数据库，而是"记忆的整理者"。

职责：
  - 通过 Pipeline.recall() 获取 ContextObject
  - 从 ContextObject 构建 Prompt 文本
  - 提供 Debug 信息
  - 未来：记忆整合、遗忘机制、长期摘要

不做的事：
  - 不直接读 Event Log（Pipeline 负责）
  - 不直接调用 Projection（Pipeline 负责）
  - 不做推理（调用方 AI 负责）
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .interaction_pipeline import InteractionPipeline
from .protocol import ContextObject
from .prompt_adapter import get_adapter


@dataclass
class MemoryResult:
    """Memory Engine 的输出"""
    context: ContextObject
    prompt_text: str
    debug_info: dict
    metadata: dict = field(default_factory=dict)


class MemoryEngine:
    """关系记忆引擎

    通过 Pipeline.recall() 获取 ContextObject，不再直接读 Event Log。

    使用示例:
        engine = MemoryEngine(pipeline=pipeline)
        result = engine.recall("小雨", query="喜欢什么")
    """

    def __init__(
        self,
        pipeline: InteractionPipeline,
        adapter_name: str = "default",
    ):
        self.pipeline = pipeline
        self._adapter = get_adapter(adapter_name)

    def recall(self, person_name: str, query: str = "", conversation_id: str = "") -> MemoryResult:
        """回忆：为某个人构建完整的记忆上下文

        1. pipeline.recall() 获取 ContextObject
        2. 从 ContextObject 构建 Prompt 文本
        3. 构建 Debug 信息
        """
        # 1. Pipeline.recall() — 唯一读出口
        ctx = self.pipeline.recall(person_name)

        # 2. 用 PromptAdapter 生成 Prompt（不再硬编码拼接）
        prompt_text = self._adapter.build(ctx)

        # 3. Debug 信息
        debug_info = {
            "person_name": person_name,
            "total_events": ctx.system.event_count if ctx.system else 0,
            "fact_count": ctx.memory.fact_count if ctx.memory else 0,
            "stage": ctx.relationship.stage if ctx.relationship else "",
            "prompt_length": len(prompt_text),
        }

        # 4. Metadata
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "person_name": person_name,
            "conversation_id": conversation_id,
            "total_events": ctx.system.event_count if ctx.system else 0,
            "prompt_length": len(prompt_text),
        }

        return MemoryResult(
            context=ctx,
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

        ctx = result.context
        if ctx.identity:
            lines.append(f"人物: {ctx.identity.name}")
            if ctx.identity.birthday:
                lines.append(f"生日: {ctx.identity.birthday}")
            if ctx.identity.tags:
                lines.append(f"标签: {', '.join(ctx.identity.tags)}")

        if ctx.memory and ctx.memory.active_facts:
            lines.append(f"记忆: {ctx.memory.fact_count} 条")
            for f in ctx.memory.active_facts[:5]:
                lines.append(f"  [{f.category}] {f.content}")

        if ctx.relationship:
            lines.append(f"\n关系: {ctx.relationship.stage}")
            lines.append(f"好感度: {ctx.relationship.chemistry}")

        lines.append(f"\n--- Prompt 内容 ---")
        lines.append(result.prompt_text[:500])

        return "\n".join(lines)
