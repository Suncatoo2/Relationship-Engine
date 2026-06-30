"""Architecture CI Audit — 自动扫描 Pipeline 旁路

这些 tests 每次 pytest 都跑，把 ADR 铁律变成可执行检查。

ADR-005: 高层只有一个入口 — publish_interaction()
ADR-006: 只有 Pipeline 可以访问 Event Store
ADR-010: Pipeline.recall() 返回 PipelineResponse

原则：如果任何代码绕过了 Pipeline，测试就失败。
"""

import ast
import os
import sys
import importlib
import textwrap
from pathlib import Path


# ---- Helpers ----

SRC_DIR = Path(__file__).parent.parent.parent / "src"


def _parse_file(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _find_import_names(tree: ast.AST) -> set[str]:
    """Return all top-level names imported into a module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    return names


def _walk_ast_calls(tree: ast.AST) -> list[tuple[str, str, int]]:
    """Return all function/method calls: (func_name, attribute_of, lineno)."""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append((func.id, "", func.lineno))
            elif isinstance(func, ast.Attribute):
                obj = ast.unparse(func.value) if hasattr(ast, "unparse") else ""
                calls.append((func.attr, obj, func.lineno))
    return calls


def _walk_ast_method_calls(tree: ast.AST) -> list[tuple[str, str, int]]:
    """Return method calls on objects: (method_name, object_expression, lineno)."""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            try:
                obj = ast.unparse(node.func.value)
            except Exception:
                obj = ""
            calls.append((node.func.attr, obj, node.lineno))
    return calls


# ============================================================
#  ADR-005: 只有一个高层入口 — publish_interaction()
# ============================================================

class TestADR005SingleEntryPoint:
    """ADR-005: 高层只有一个入口 — publish_interaction()

    禁止任何代码绕过 Pipeline.publish() 直接调用:
      - Storage.append()
      - Dispatcher.dispatch()
      - create_event() + Storage.append() 组合
    """

    def test_mcp_server_no_storage_append(self):
        """mcp_server.py 不得直接调用 Storage.append()"""
        path = SRC_DIR / "mcp_server.py"
        tree = _parse_file(path)
        method_calls = _walk_ast_method_calls(tree)
        violations = [
            (obj, method, line)
            for method, obj, line in method_calls
            if method == "append" and ("storage" in obj.lower() or "_storage" in obj.lower())
        ]
        assert len(violations) == 0, (
            f"ADR-005 VIOLATION: mcp_server.py 直接调用了 Storage.append() 在行: {violations}\n"
            f"所有写入必须经过 Pipeline.publish()。"
        )

    def test_mcp_server_no_dispatcher_dispatch(self):
        """mcp_server.py 不得直接调用 Dispatcher.dispatch()"""
        path = SRC_DIR / "mcp_server.py"
        tree = _parse_file(path)
        method_calls = _walk_ast_method_calls(tree)
        violations = [
            (obj, method, line)
            for method, obj, line in method_calls
            if method == "dispatch" and ("dispatcher" in obj.lower() or "_dispatcher" in obj.lower())
        ]
        assert len(violations) == 0, (
            f"ADR-005 VIOLATION: mcp_server.py 直接调用了 Dispatcher.dispatch() 在行: {violations}\n"
            f"所有写入必须经过 Pipeline.publish()。"
        )

    def test_web_server_no_storage_append(self):
        """web_server.py 不得直接调用 Storage.append()"""
        path = SRC_DIR / "web_server.py"
        tree = _parse_file(path)
        method_calls = _walk_ast_method_calls(tree)
        violations = [
            (obj, method, line)
            for method, obj, line in method_calls
            if method == "append" and ("storage" in obj.lower() or "_storage" in obj.lower())
        ]
        assert len(violations) == 0, (
            f"ADR-005 VIOLATION: web_server.py 直接调用了 Storage.append() 在行: {violations}\n"
            f"所有写入必须经过 Pipeline.publish()。"
        )

    def test_web_server_no_dispatcher_dispatch(self):
        """web_server.py 不得直接调用 Dispatcher.dispatch()"""
        path = SRC_DIR / "web_server.py"
        tree = _parse_file(path)
        method_calls = _walk_ast_method_calls(tree)
        violations = [
            (obj, method, line)
            for method, obj, line in method_calls
            if method == "dispatch" and ("dispatcher" in obj.lower() or "_dispatcher" in obj.lower())
        ]
        assert len(violations) == 0, (
            f"ADR-005 VIOLATION: web_server.py 直接调用了 Dispatcher.dispatch() 在行: {violations}\n"
            f"所有写入必须经过 Pipeline.publish()。"
        )


# ============================================================
#  ADR-006: 只有 Pipeline 可以访问 Event Store
# ============================================================

class TestADR006PipelineOnly:
    """ADR-006: 只有 Pipeline 可以访问 Event Store

    禁止:
      - Projection 直接调用 Storage.read()
      - Projection 直接调用 Storage.append()
      - MemoryEngine 直接访问 EventLog
    """

    def test_no_projection_reads_storage_directly(self):
        """所有 Projection 不得直接导入或调用 Storage"""
        proj_dir = SRC_DIR / "projections"
        SKIP = {"__init__.py", "base.py", "context.py", "prompt_builder.py"}
        for py_file in proj_dir.glob("*.py"):
            if py_file.name in SKIP:
                continue  # Infrastructure, deprecated, or encoding issues
            tree = _parse_file(py_file)
            import_names = _find_import_names(tree)
            violations = []
            for name in import_names:
                if "storage" in name.lower() and name != "storage":
                    violations.append(name)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "storage" in node.module.lower():
                        violations.append("from {} import ...".format(node.module))
            assert len(violations) == 0, (
                "ADR-006 VIOLATION: {} 导入了 Storage 相关模块: {}\n"
                "Projection 只能消费 Event，不能主动读 Storage。".format(py_file.name, violations)
            )

    def test_no_projection_calls_storage_read(self):
        """Projection 不得调用 .read_all() 或 .read_since() 等 Storage 方法"""
        proj_dir = SRC_DIR / "projections"
        SKIP = {"__init__.py", "base.py", "context.py", "prompt_builder.py"}
        for py_file in proj_dir.glob("*.py"):
            if py_file.name in SKIP:
                continue
            tree = _parse_file(py_file)
            method_calls = _walk_ast_method_calls(tree)
            storage_methods = {"read_all", "read_since", "read", "count"}
            violations = [
                (obj, method, line)
                for method, obj, line in method_calls
                if method in storage_methods
            ]
            assert len(violations) == 0, (
                "ADR-006 VIOLATION: {} 调用了 Storage 读方法: {}\n"
                "Projection 只能消费传入的 Event，不能主动读 Storage。".format(py_file.name, violations)
            )

    def test_memory_engine_no_direct_storage_access(self):
        """MemoryEngine 不得直接访问 Storage（应通过 Pipeline）"""
        path = SRC_DIR / "memory_engine.py"
        tree = _parse_file(path)
        method_calls = _walk_ast_method_calls(tree)
        storage_methods = {"read_all", "read_since", "count"}
        violations = [
            (obj, method, line)
            for method, obj, line in method_calls
            if method in storage_methods and "storage" in obj.lower()
        ]
        # Also verify no Storage import
        import_names = _find_import_names(tree)
        storage_imports = [n for n in import_names if "storage" in n.lower()
                          and n not in ("storage", "_storage")]
        assert len(violations) == 0 and len(storage_imports) == 0, (
            "ADR-006 VIOLATION: memory_engine.py 直接使用了 Storage: calls={}, imports={}\n"
            "MemoryEngine 只能通过 Pipeline 访问数据。".format(violations, storage_imports)
        )


# ============================================================
#  ADR-010: Pipeline.recall() 返回 PipelineResponse（不是裸 ContextObject）
# ============================================================

class TestADR010PipelineResponse:
    """ADR-010: Pipeline.recall() 返回 PipelineResponse

    PipelineResponse 必须包含 context + metadata + diagnostics。
    """

    def test_pipeline_response_has_required_fields(self):
        """PipelineResponse 必须有 context, metadata, diagnostics 三个字段"""
        from src.pipeline_response import PipelineResponse
        # Verify the class exists with the right shape
        import dataclasses
        fields = {f.name: f.type for f in dataclasses.fields(PipelineResponse)}
        assert "context" in fields, "PipelineResponse 必须有 context 字段"
        assert "metadata" in fields, "PipelineResponse 必须有 metadata 字段"
        assert "diagnostics" in fields, "PipelineResponse 必须有 diagnostics 字段"

    def test_pipeline_recall_returns_pipeline_response(self):
        """Pipeline.recall() 的返回类型是 PipelineResponse"""
        import inspect
        from src.interaction_pipeline import InteractionPipeline
        sig = inspect.signature(InteractionPipeline.recall)
        return_annotation = sig.return_annotation
        return_str = str(return_annotation)
        assert "PipelineResponse" in return_str, (
            f"Pipeline.recall() 返回类型必须是 PipelineResponse，当前: {return_str}"
        )


# ============================================================
#  Pipeline 旁路综合扫描 — 全量检查
# ============================================================

class TestNoPipelineBypass:
    """全量扫描：任何 src/ 下的业务代码都不得绕过 Pipeline"""

    EXCLUDED_FILES = {
        "storage.py",        # Storage 本身
        "dispatcher.py",     # Dispatcher 本身（由 Pipeline 调用）
        "interaction_pipeline.py",  # Pipeline 本身
        "__init__.py",
    }

    def test_no_source_file_bypasses_pipeline_write(self):
        """src/ 下所有非基础设施文件不得直接调用 Storage.append()"""
        src_dir = SRC_DIR
        violations = []
        for py_file in src_dir.glob("*.py"):
            if py_file.name in self.EXCLUDED_FILES:
                continue
            tree = _parse_file(py_file)
            method_calls = _walk_ast_method_calls(tree)
            for method, obj, line in method_calls:
                if method == "append" and obj:
                    # Allow Pipeline._snapshot_mgr calls and tests, not storage
                    is_snapshot = "snapshot" in obj.lower()
                    is_storage = "storage" in obj.lower() or "_storage" in obj.lower()
                    is_storage_var = obj in ("storage", "_storage")
                    if not is_snapshot and (is_storage or is_storage_var):
                        violation = "{}:{} → {}.{}()".format(py_file.name, line, obj, method)
                        violations.append(violation)

        assert len(violations) == 0, (
            "PIPELINE BYPASS DETECTED:\n"
            + "\n".join("  ❌ " + v for v in violations)
            + "\n\n所有写入必须经过 Pipeline.publish()。"
        )

    def test_all_servers_use_create_pipeline(self):
        """所有 Server 入口都使用 create_pipeline() 工厂初始化"""
        server_files = ["web_server.py", "mcp_server.py"]
        for fname in server_files:
            path = SRC_DIR / fname
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            assert "create_pipeline" in content, (
                f"ARCHITECTURE VIOLATION: {fname} 未使用 create_pipeline() 工厂。\n"
                f"所有 Server 必须通过 create_pipeline() 统一初始化 Pipeline。"
            )


# ============================================================
#  Consumer Facade Enforcement — Post Consumer Unification
# ============================================================

class TestConsumerFacadeEnforcement:
    """Phase 1: enforce ConsumerFacade as the single consumer entry point.

    After Consumer Unification, all consumer files (mcp_server, web_server,
    future cli/api) MUST use ConsumerFacade for reads. Direct Pipeline.recall()
    or Storage access in consumer files is a regression.
    """

    CONSUMER_FILES = ["web_server.py", "mcp_server.py"]

    def test_consumer_files_import_consumer_facade(self):
        """All consumer files must import ConsumerFacade."""
        for fname in self.CONSUMER_FILES:
            path = SRC_DIR / fname
            content = path.read_text(encoding="utf-8")
            assert "ConsumerFacade" in content, (
                f"CONSUMER FACADE VIOLATION: {fname} does not import ConsumerFacade.\n"
                f"All consumers must use ConsumerFacade as the single entry point."
            )

    def test_consumer_files_do_not_import_storage(self):
        """Consumer files must not import Storage directly."""
        for fname in self.CONSUMER_FILES:
            path = SRC_DIR / fname
            tree = _parse_file(path)
            import_names = _find_import_names(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "storage" in node.module:
                        aliases = [a.name for a in node.names]
                        assert False, (
                            f"CONSUMER FACADE VIOLATION: {fname} imports from storage module: {aliases}.\n"
                            f"All data access must go through ConsumerFacade, not Storage directly."
                        )

    def test_no_consumer_bypasses_pipeline_recall(self):
        """Consumer files must not call Pipeline.recall() directly.

        All recall() calls must go through ConsumerFacade.recall().
        """
        for fname in self.CONSUMER_FILES:
            path = SRC_DIR / fname
            tree = _parse_file(path)
            method_calls = _walk_ast_method_calls(tree)
            violations = [
                (obj, method, line)
                for method, obj, line in method_calls
                if method == "recall" and "_pipeline" in obj
            ]
            assert len(violations) == 0, (
                f"CONSUMER FACADE VIOLATION: {fname} calls Pipeline.recall() directly "
                f"at lines: {violations}.\n"
                f"All recall() calls must go through ConsumerFacade.recall()."
            )
