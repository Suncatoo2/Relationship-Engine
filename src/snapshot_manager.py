"""SnapshotManager — Projection 快照管理

Snapshot 是 Projection 结果的持久化副本，目的是加速。
不是新的数据源，不替代 Event Log（ADR-006 原则 #6）。

格式:
  data/{user_id}/snapshots/{projection_name}.json

  {
    "projection": "FactProjection",
    "version": 1,
    "generated_at": "2026-06-28T...",
    "last_event_id": "abc-123",
    "last_calculated_timestamp": "2026-06-28T...",
    "state": { ... }
  }

使用:
  snapshot = SnapshotManager("data/local_default")
  snapshot.save("FactProjection", state_dict, "event_42")
  state, event_id = snapshot.load("FactProjection")
"""

import json
import os
from datetime import datetime, timezone


class SnapshotManager:
    """Projection 快照管理器

    职责:
      - save(): 保存 Projection 状态快照
      - load(): 加载快照（用于 Incremental Replay）
      - verify(): 验证快照是否仍然有效（last_event_id 在 Event Log 中存在）
    """

    def __init__(self, data_dir: str = "data"):
        self.snapshot_dir = os.path.join(data_dir, "snapshots")

    def save(self, projection_name: str, state: dict, last_event_id: str) -> str:
        """保存 Projection 快照

        Args:
            projection_name: Projection 类名（如 "FactProjection"）
            state: Projection.snapshot() 或 Projection.project().to_dict() 返回的 dict
            last_event_id: 该快照对应的最后一个 event_id

        Returns:
            快照文件路径
        """
        os.makedirs(self.snapshot_dir, exist_ok=True)

        snapshot = {
            "projection": projection_name,
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "last_event_id": last_event_id,
            "last_calculated_timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state,
        }

        filepath = os.path.join(self.snapshot_dir, f"{projection_name.lower()}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        return filepath

    def load(self, projection_name: str) -> tuple[dict | None, str]:
        """加载 Projection 快照

        Args:
            projection_name: Projection 类名

        Returns:
            (state_dict, last_event_id) — 如果快照不存在，返回 (None, "")
        """
        filepath = os.path.join(self.snapshot_dir, f"{projection_name.lower()}.json")
        if not os.path.exists(filepath):
            return None, ""

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("state"), data.get("last_event_id", "")

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
