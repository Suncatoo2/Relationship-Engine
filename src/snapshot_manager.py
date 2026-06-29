"""SnapshotManager — Projection 快照管理

Snapshot 是 Projection 结果的持久化副本，目的是加速。
不是新的数据源，不替代 Event Log（ADR-006 原则 #6）。

格式:
  data/{user_id}/snapshots/{projection_name}.json

  {
    "projection": "FactProjection",
    "schema_version": 1,
    "projection_version": 1,
    "generated_at": "2026-06-28T...",
    "last_event_id": "abc-123",
    "last_calculated_timestamp": "2026-06-28T...",
    "checksum": "sha256hex...",
    "state": { ... }
  }

兼容性: load() 验证 schema_version。不匹配 → fallback to full rebuild。
"""

import json
import os
import hashlib
from datetime import datetime, timezone

# 当前 schema 版本—修改 snapshot 结构时递增
SNAPSHOT_SCHEMA_VERSION = 1


class SnapshotManager:
    """Projection 快照管理器"""

    def __init__(self, data_dir: str = "data"):
        self.snapshot_dir = os.path.join(data_dir, "snapshots")

    def save(self, projection_name: str, state: dict, last_event_id: str,
             projection_version: int = 1) -> str:
        """保存 Projection 快照"""
        os.makedirs(self.snapshot_dir, exist_ok=True)

        state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
        checksum = hashlib.sha256(state_json.encode()).hexdigest()[:16]

        snapshot = {
            "projection": projection_name,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "projection_version": projection_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "last_event_id": last_event_id,
            "last_calculated_timestamp": datetime.now(timezone.utc).isoformat(),
            "checksum": checksum,
            "state": state,
        }

        filepath = os.path.join(self.snapshot_dir, f"{projection_name.lower()}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        return filepath

    def load(self, projection_name: str) -> tuple[dict | None, str]:
        """加载 Projection 快照

        兼容性验证:
          - schema_version 不匹配 → 返回 (None, "") — 触发全量重建
          - checksum 不匹配 → 返回 (None, "") — 数据损坏

        Returns:
            (state_dict, last_event_id) — 如果无效，返回 (None, "")
        """
        filepath = os.path.join(self.snapshot_dir, f"{projection_name.lower()}.json")
        if not os.path.exists(filepath):
            return None, ""

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Gate 1: schema version validation
        if data.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            return None, ""

        # Gate 1: checksum validation
        state = data.get("state")
        if state:
            state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
            expected_checksum = hashlib.sha256(state_json.encode()).hexdigest()[:16]
            if data.get("checksum") != expected_checksum:
                return None, ""

        return state, data.get("last_event_id", "")

    def verify(self, projection_name: str, event_ids: set[str]) -> bool:
        """验证快照是否仍然有效

        检查快照的 last_event_id 是否在 Event Log 中存在。

        Args:
            projection_name: Projection 类名
            event_ids: Event Log 中所有 event_id 的集合

        Returns:
            True = 有效，False = 需要重建
        """
        _, last_id = self.load(projection_name)
        if not last_id:
            return False
        return last_id in event_ids

    def save_all(self, snapshots: dict[str, dict], last_event_id: str) -> list[str]:
        """保存所有 Projection 的快照

        Args:
            snapshots: {projection_name: state_dict}
            last_event_id: 统一的最后一个 event_id

        Returns:
            保存的文件路径列表
        """
        paths = []
        for name, state in snapshots.items():
            paths.append(self.save(name, state, last_event_id))
        return paths

    def list_snapshots(self) -> list[str]:
        """列出所有快照文件"""
        if not os.path.exists(self.snapshot_dir):
            return []
        return [
            f[:-5] for f in os.listdir(self.snapshot_dir)
            if f.endswith(".json")
        ]

    def clear(self) -> None:
        """清空所有快照（仅用于测试）"""
        for name in self.list_snapshots():
            os.remove(os.path.join(self.snapshot_dir, f"{name}.json"))
