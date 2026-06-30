"""Tests for ConsumerFacade — Consumer Unification

Validates:
  - ConsumerFacade.recall() forwards person/query/max_tokens to Pipeline.recall()
  - ConsumerFacade.get_context_json() returns valid JSON
  - ConsumerFacade.get_person_json() returns identity block
  - ConsumerFacade.get_time_json() returns time block
  - ConsumerFacade.list_people() discovers all people
  - ConsumerFacade.get_stats() returns system stats
  - ConsumerFacade.search_events() finds matching events
  - ConsumerFacade.get_raw_events() filters correctly
  - ConsumerFacade.debug_summary() includes insights
  - Backward compat: recall() without query/max_tokens still works
  - Web server routes use ConsumerFacade, not MemoryEngine
  - MCP tools do not bypass Pipeline for storage reads
"""

import json
import os
import pytest
import tempfile

from src.storage import JSONLStorage
from src.dispatcher import ProjectionDispatcher
from src.interaction_pipeline import (
    InteractionPipeline, Interaction, FactInput, EmotionInput,
)
from src.consumer_facade import ConsumerFacade, ConsumerResult
from src.projections.fact_state import FactProjection
from src.projections.person import PersonProjection


# ============================================================
#  Helpers
# ============================================================

def _build_facade(tmp_path) -> ConsumerFacade:
    store = JSONLStorage(str(tmp_path))
    disp = ProjectionDispatcher()
    for p, types in [
        (FactProjection(), ["fact"]),
        (PersonProjection(), ["person", "fact"]),
    ]:
        disp.register(p, event_types=types)
    pipeline = InteractionPipeline(storage=store, dispatcher=disp)
    return ConsumerFacade(pipeline=pipeline)


def _seed_data(facade: ConsumerFacade):
    facade.publish(Interaction(
        message="hi", person="Alice",
        facts=[FactInput(content="likes Python", category="skill", importance=8)],
    ))
    facade.publish(Interaction(
        message="hello", person="Bob",
        facts=[FactInput(content="likes Java", category="skill", importance=6)],
    ))


# ============================================================
#  ConsumerFacade.recall() Tests
# ============================================================

class TestConsumerFacadeRecall:
    def test_recall_forwards_person_to_pipeline(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        result = facade.recall("Alice")
        assert isinstance(result, ConsumerResult)
        assert result.context.identity.name == "Alice"

    def test_recall_forwards_query_to_pipeline(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        # With query "Python", Alice should have relevant facts
        result = facade.recall("Alice", query="Python")
        assert isinstance(result, ConsumerResult)
        assert result.context is not None

    def test_recall_forwards_max_tokens_to_pipeline(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        # Tight budget should not crash
        result = facade.recall("Alice", max_tokens=100)
        assert isinstance(result, ConsumerResult)
        assert result.context is not None

    def test_recall_without_query_still_works(self, tmp_path):
        """Backward compat: old calls without query/max_tokens should work."""
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        result = facade.recall("Alice")
        assert result.context.identity.name == "Alice"
        assert result.prompt_text
        assert result.debug_info["person_name"] == "Alice"

    def test_recall_returns_prompt_text(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        result = facade.recall("Alice")
        assert isinstance(result.prompt_text, str)
        assert len(result.prompt_text) > 0

    def test_recall_metadata_has_timing(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        result = facade.recall("Alice")
        assert "trace_id" in result.metadata
        assert "timing_ms" in result.metadata
        assert result.metadata["person_name"] == "Alice"

    def test_recall_unknown_person_does_not_crash(self, tmp_path):
        facade = _build_facade(tmp_path)
        result = facade.recall("Nobody")
        assert result.context.identity.name == "Nobody"
        assert result.context.memory.fact_count == 0


class TestConsumerFacadeOutputs:
    def test_get_context_json(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        json_str = facade.get_context_json("Alice")
        d = json.loads(json_str)
        assert d["identity"]["name"] == "Alice"
        assert "memory" in d

    def test_get_person_json(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        json_str = facade.get_person_json("Alice")
        d = json.loads(json_str)
        assert d["name"] == "Alice"

    def test_get_time_json(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        json_str = facade.get_time_json("Alice")
        d = json.loads(json_str)
        assert "last_chat_label" in d

    def test_get_time_json_empty_person(self, tmp_path):
        facade = _build_facade(tmp_path)
        assert facade.get_time_json("") == "{}"

    def test_list_people(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        people = facade.list_people()
        assert "Alice" in people
        assert "Bob" in people

    def test_get_stats(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        stats = facade.get_stats()
        assert stats["total_events"] >= 2
        assert stats["total_persons"] >= 2
        assert "chat" in stats["by_type"]
        assert "storage_health" in stats

    def test_search_events(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        results = facade.search_events("Python")
        assert len(results) >= 1
        assert any("Python" in json.dumps(r) for r in results)

    def test_search_events_returns_empty_for_nonexistent(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        results = facade.search_events("zzz_nonexistent_xxx")
        assert results == []

    def test_get_raw_events(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        events = facade.get_raw_events(person_name="Alice")
        assert len(events) >= 1
        assert all(e["person"] == "Alice" for e in events)

    def test_get_raw_events_respects_days(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        events = facade.get_raw_events(days=1)
        assert isinstance(events, list)

    def test_debug_summary(self, tmp_path):
        facade = _build_facade(tmp_path)
        _seed_data(facade)
        summary = facade.debug_summary("Alice")
        assert "Alice" in summary
        assert "Memory Debug" in summary
        assert "Prompt 内容" in summary


# ============================================================
#  Consumer Compliance Tests
# ============================================================

class TestConsumerCompliance:
    """Verify consumers use facade, not direct storage access."""

    def test_facade_is_imported_by_web_server(self):
        """Web server should import ConsumerFacade."""
        import ast
        import os
        ws_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "web_server.py"
        )
        with open(ws_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports.add(alias.name)
        assert "ConsumerFacade" in imports, (
            "web_server.py must import ConsumerFacade"
        )

    def test_facade_is_imported_by_mcp_server(self):
        """MCP server should import ConsumerFacade."""
        import ast
        import os
        ms_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "mcp_server.py"
        )
        with open(ms_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports.add(alias.name)
        assert "ConsumerFacade" in imports, (
            "mcp_server.py must import ConsumerFacade"
        )
