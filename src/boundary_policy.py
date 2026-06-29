"""Boundary Policy — Knowledge Boundary 阈值管理

Business Policy 与 Business Mechanism 解耦。
阈值从 config/decay_config.json 读取，代码不持有 magic numbers。
"""

import json
import os


class BoundaryPolicy:
    """知识边界注入策略"""

    _config = None

    @classmethod
    def _load_config(cls):
        if cls._config is not None:
            return cls._config
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "decay_config.json"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            cls._config = {}  # fallback: use class defaults
        return cls._config

    @classmethod
    def _get(cls, section: str, key: str, default):
        config = cls._load_config()
        return config.get(section, {}).get(key, default)

    # ---- 阈值（从 config 读取，有类默认值 fallback）----

    @classmethod
    def outdated_threshold(cls) -> int:
        return cls._get("boundary_policy", "outdated_threshold_days", 30)

    @classmethod
    def insufficient_threshold(cls) -> int:
        return cls._get("boundary_policy", "insufficient_threshold_days", 60)

    @classmethod
    def outdated_confidence(cls) -> float:
        return cls._get("boundary_policy", "outdated_confidence", 0.25)

    @classmethod
    def insufficient_confidence(cls) -> float:
        return cls._get("boundary_policy", "insufficient_confidence", 0.08)

    @classmethod
    def outdated_importance(cls) -> int:
        return cls._get("boundary_policy", "outdated_importance", 7)

    @classmethod
    def insufficient_importance(cls) -> int:
        return cls._get("boundary_policy", "insufficient_importance", 9)

    @classmethod
    def outdated_message(cls, person: str, days: int) -> str:
        return (
            f"The engine's knowledge about {person} is becoming outdated. "
            f"Last interaction was {days} days ago."
        )

    @classmethod
    def insufficient_message(cls, person: str, days: int) -> str:
        return (
            f"The engine has insufficient evidence about {person}'s recent state. "
            f"No interaction in {days} days."
        )
