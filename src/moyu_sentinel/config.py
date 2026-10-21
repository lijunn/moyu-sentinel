"""配置读取、校验与持久化。

作者：LiJun
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import data_dir


@dataclass(slots=True)
class NormalizedRect:
    """使用 0～1 坐标保存的矩形，避免依赖摄像头分辨率。"""

    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0

    def validate(self) -> "NormalizedRect":
        x = min(max(float(self.x), 0.0), 1.0)
        y = min(max(float(self.y), 0.0), 1.0)
        width = min(max(float(self.width), 0.01), 1.0 - x)
        height = min(max(float(self.height), 0.01), 1.0 - y)
        return NormalizedRect(x=x, y=y, width=width, height=height)


@dataclass(slots=True)
class AppConfig:
    """MoyuSentinel 可持久化配置。"""

    camera_index: int = 0
    confidence: float = 0.55
    hold_seconds: float = 0.8
    cooldown_seconds: float = 15.0
    danger_zone: NormalizedRect = field(default_factory=NormalizedRect)
    shortcut: str = "Command+Tab"

    def validate(self) -> "AppConfig":
        return AppConfig(
            camera_index=min(max(int(self.camera_index), 0), 8),
            confidence=min(max(float(self.confidence), 0.1), 0.95),
            hold_seconds=min(max(float(self.hold_seconds), 0.5), 1.0),
            cooldown_seconds=min(max(float(self.cooldown_seconds), 10.0), 30.0),
            danger_zone=self.danger_zone.validate(),
            shortcut=str(self.shortcut).strip() or "Command+Tab",
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        zone_raw = raw.get("danger_zone", {})
        zone = NormalizedRect(
            x=zone_raw.get("x", 0.0),
            y=zone_raw.get("y", 0.0),
            width=zone_raw.get("width", 1.0),
            height=zone_raw.get("height", 1.0),
        )
        return cls(
            camera_index=raw.get("camera_index", 0),
            confidence=raw.get("confidence", 0.55),
            hold_seconds=raw.get("hold_seconds", 0.8),
            cooldown_seconds=raw.get("cooldown_seconds", 15.0),
            danger_zone=zone,
            shortcut=raw.get("shortcut", "Command+Tab"),
        ).validate()


def config_path() -> Path:
    return data_dir() / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    """读取配置；文件缺失或损坏时安全回退到默认值。"""

    target = path or config_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("配置根节点必须是对象")
        return AppConfig.from_dict(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """通过原子替换写入配置，避免异常退出留下半个 JSON 文件。"""

    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(config.validate()), ensure_ascii=False, indent=2)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="config-", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass

