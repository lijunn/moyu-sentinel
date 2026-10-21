"""配置模块测试。作者：LiJun。"""

from pathlib import Path

import pytest

from moyu_sentinel.config import AppConfig, NormalizedRect, load_config, save_config


def test_config_validation_clamps_values() -> None:
    config = AppConfig(
        camera_index=-4,
        confidence=2.0,
        hold_seconds=0.1,
        cooldown_seconds=99,
        danger_zone=NormalizedRect(-1, 0.9, 4, 4),
        shortcut="",
    ).validate()
    assert config.camera_index == 0
    assert config.confidence == 0.95
    assert config.hold_seconds == 0.5
    assert config.cooldown_seconds == 30.0
    assert config.danger_zone.x == 0.0
    assert config.danger_zone.height == pytest.approx(0.1)
    assert config.shortcut == "Command+Tab"


def test_broken_config_falls_back_to_default(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("{broken", encoding="utf-8")
    assert load_config(target) == AppConfig()


def test_config_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    expected = AppConfig(shortcut="Control+2", danger_zone=NormalizedRect(0.1, 0.2, 0.5, 0.6))
    save_config(expected, target)
    assert load_config(target) == expected

