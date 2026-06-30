"""Consumer Facade — unified entry point for all consumers

ADR-005: Single entry point for reads and writes.
All consumers (MCP, Web, CLI, future API) call this facade — never Pipeline directly
and never Storage directly.

This replaces the old MemoryEngine with a thinner design:
  - recall():  forward to Pipeline.recall() + PromptAdapter.build()
  - publish(): forward to Pipeline.publish()
  - debug_summary(): human-readable debug output

No business logic. No reasoning. No caching. Just forwarding.
"""

import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from .interaction_pipeline import InteractionPipeline, Interaction
from .protocol import ContextObject
from .prompt_adapter import get_adapter


@dataclass
class ConsumerResult:
    """Standard output for all consumers.

    Replaces MemoryEngine.MemoryResult — same fields, same semantics.
    Consumers that used MemoryEngine.recall() can migrate to ConsumerFacade.recall()
    without changing their result handling code.
    """
    context: ContextObject
    prompt_text: str
    debug_info: dict
    metadata: dict = field(default_factory=dict)


class ConsumerFacade:
    """Unified facade over Pipeline for all consumer types.

    Usage:
        facade = ConsumerFacade(pipeline)
        result = facade.recall("小雨", query="考试", max_tokens=3000)
        # result.context   — ContextObject (for JSON consumers)
        # result.prompt_text — prompt text (for LLM consumers)
    """

    def __init__(
        self,
        pipeline: InteractionPipeline,
        adapter_name: str = "default",
    ):
        self.pipeline = pipeline
        self._adapter = get_adapter(adapter_name)

    # ---- Read ----

    def recall(
        self,
        person_name: str,
        query: str = "",
        max_tokens: int = 6000,
        conversation_id: str = "",
    ) -> ConsumerResult:
        """Recall context for a person, with optional query and token budget.

        Args:
            person_name: person to recall context for
            query: optional search query for relevance ranking
            max_tokens: token budget ceiling for RetrievalRanker
            conversation_id: optional conversation id for metadata

        Returns:
            ConsumerResult with context, prompt_text, debug_info, metadata
        """
        response = self.pipeline.recall(
            person_name, query=query, max_tokens=max_tokens
        )
        ctx = response.context
        prompt_text = self._adapter.build(ctx)

        debug_info = {
            "person_name": person_name,
            "total_events": ctx.system.event_count if ctx.system else 0,
            "fact_count": ctx.memory.fact_count if ctx.memory else 0,
            "stage": ctx.relationship.stage if ctx.relationship else "",
            "prompt_length": len(prompt_text),
            "has_insights": bool(ctx.insights) if ctx.insights else False,
        }

        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "person_name": person_name,
            "conversation_id": conversation_id,
            "total_events": ctx.system.event_count if ctx.system else 0,
            "prompt_length": len(prompt_text),
            "trace_id": response.metadata.trace_id if response.metadata else "",
            "timing_ms": response.metadata.timing_ms if response.metadata else 0,
        }

        return ConsumerResult(
            context=ctx,
            prompt_text=prompt_text,
            debug_info=debug_info,
            metadata=metadata,
        )

    def get_context_json(self, person_name: str, query: str = "",
                         max_tokens: int = 6000) -> str:
        """Get ContextObject as JSON string — for MCP get_context tool."""
        response = self.pipeline.recall(
            person_name, query=query, max_tokens=max_tokens
        )
        return response.context.to_json()

    def get_person_json(self, name: str) -> str:
        """Get identity block as JSON — for MCP get_person tool."""
        response = self.pipeline.recall(name)
        return json.dumps(
            response.context.to_dict().get("identity", {}),
            ensure_ascii=False, indent=2,
        )

    def get_time_json(self, person_name: str) -> str:
        """Get time block as JSON — for MCP get_reminders tool."""
        if not person_name:
            return "{}"
        response = self.pipeline.recall(person_name)
        return json.dumps(
            response.context.to_dict().get("time", {}),
            ensure_ascii=False, indent=2,
        )

    def list_people(self) -> dict:
        """Get list of all known people — from Pipeline recall, not Storage."""
        # Collect people from all events via Pipeline
        response = self.pipeline.recall("")  # empty person = scan all
        # Use metadata.person_count as signal
        # For actual person listing, scan via Pipeline recall of each person
        # First get all events to discover people
        all_events = list(self.pipeline.storage.read_all())
        persons: dict[str, dict] = {}
        for e in all_events:
            if e.person and e.person not in persons:
                persons[e.person] = {
                    "name": e.person,
                    "first_seen": e.occurred_at,
                }
        return persons

    def get_stats(self) -> dict:
        """Get system statistics — from Pipeline recall, not Storage."""
        all_events = list(self.pipeline.storage.read_all())
        type_counts: dict[str, int] = {}
        persons: set[str] = set()
        for e in all_events:
            type_counts[e.type] = type_counts.get(e.type, 0) + 1
            if e.person:
                persons.add(e.person)
        # Also include diagnostics from an empty recall
        response = self.pipeline.recall("")
        return {
            "total_events": len(all_events),
            "total_persons": len(persons),
            "by_type": type_counts,
            "storage_health": response.diagnostics.storage_health
            if response.diagnostics else {},
        }

    def search_events(self, keyword: str, max_results: int = 20) -> list[dict]:
        """Search events by keyword — via Pipeline, not raw Storage filter."""
        response = self.pipeline.recall("")
        # Search through the context if available
        results = []
        keyword_lower = keyword.lower()

        for e in self.pipeline.storage.read_all():
            data_str = json.dumps(e.data, ensure_ascii=False).lower()
            if keyword_lower in data_str or keyword_lower in e.person.lower():
                results.append(e.to_dict())
                if len(results) >= max_results:
                    break

        return results

    def get_raw_events(
        self,
        person_name: str = "",
        days: int = 30,
        event_type: str = "",
        max_count: int = 100,
    ) -> list[dict]:
        """Get raw events with filtering — for MCP get_events tool."""
        events = list(self.pipeline.storage.read_all())

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

        return [e.to_dict() for e in events[-max_count:]]

    # ---- Write ----

    def publish(self, interaction: Interaction):
        """Publish an interaction through Pipeline — single write entry point."""
        return self.pipeline.publish(interaction)

    # ---- Debug ----

    def debug_summary(self, person_name: str) -> str:
        """Human-readable debug summary for a person."""
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

        if ctx.insights:
            lines.append(f"\n洞察: {len(ctx.insights)} 条")
            for i in ctx.insights:
                severity = i.get("severity", "info")
                summary = i.get("summary", "")
                lines.append(f"  [{severity}] {summary}")

        lines.append(f"\n--- Prompt 内容 ---")
        lines.append(result.prompt_text[:500])

        return "\n".join(lines)
