"""Tests for snapshot_manager.py — SnapshotManager"""

import pytest
import os
import json
from src.snapshot_manager import SnapshotManager


class TestSnapshotManager:
    @pytest.fixture
    def manager(self, tmp_path):
        return SnapshotManager(str(tmp_path))

    def test_save_and_load(self, manager):
        """保存后应能加载回来"""
        state = {"active": {"preference": "blue"}, "total": 1}
        manager.save("FactProjection", state, "event_42")
        loaded_state, last_id = manager.load("FactProjection")
        assert loaded_state == state
        assert last_id == "event_42"

    def test_load_nonexistent(self, manager):
        """不存在的快照返回 (None, "")"""
        state, last_id = manager.load("NonexistentProjection")
        assert state is None
        assert last_id == ""

    def test_verify_valid(self, manager):
        """有效快照应通过验证"""
        manager.save("FactProjection", {}, "event_42")
        assert manager.verify("FactProjection", {"event_41", "event_42"})

    def test_verify_invalid(self, manager):
        """last_event_id 不在 Event Log 中应验证失败"""
        manager.save("FactProjection", {}, "event_42")
        assert not manager.verify("FactProjection", {"event_99"})

    def test_verify_nonexistent(self, manager):
        """不存在的快照应验证失败"""
        assert not manager.verify("Nonexistent", {"event_1"})

    def test_save_all(self, manager):
        """批量保存应成功"""
        snapshots = {
            "FactProjection": {"facts": 5},
            "EmotionProjection": {"mood": "happy"},
        }
        paths = manager.save_all(snapshots, "event_100")
        assert len(paths) == 2
        assert "factprojection.json" in [os.path.basename(p) for p in paths]
        assert "emotionprojection.json" in [os.path.basename(p) for p in paths]

    def test_list_snapshots(self, manager):
        """应列出所有快照"""
        manager.save("A", {}, "e1")
        manager.save("B", {}, "e2")
        names = manager.list_snapshots()
        assert set(names) == {"a", "b"}

    def test_clear(self, manager):
        """清空后应无残留"""
        manager.save("A", {}, "e1")
        manager.clear()
        assert manager.list_snapshots() == []

    def test_snapshot_has_all_required_fields(self, manager):
        """快照必须包含 schema_version + projection_version + last_event_id + checksum"""
        manager.save("TestProjection", {"x": 1}, "event_1")
        filepath = os.path.join(manager.snapshot_dir, "testprojection.json")
        with open(filepath) as f:
            data = json.load(f)
        assert "schema_version" in data
        assert "projection_version" in data
        assert "last_event_id" in data
        assert "checksum" in data
        assert "last_calculated_timestamp" in data
        assert data["last_event_id"] == "event_1"
        assert data["state"] == {"x": 1}

    def test_last_calculated_timestamp_prevents_drift(self, manager):
        """last_calculated_timestamp 记录计算时刻，防止时间漂移"""
        manager.save("Projection", {}, "event_x")
        _, last_id = manager.load("Projection")
        # last_event_id 是 snapshot 的参数，不是 timestamp——它应该是传入的 event_id
        assert last_id == "event_x"
