"""快捷键白名单测试。作者：LiJun。"""

import pytest

from moyu_sentinel import hotkey
from moyu_sentinel.hotkey import parse_shortcut


def test_command_tab_mapping() -> None:
    parsed = parse_shortcut("Command+Tab")
    assert parsed.modifiers == ("command",)
    assert parsed.key_code == 48


def test_alias_and_number_key() -> None:
    parsed = parse_shortcut("ctrl+2")
    assert parsed.modifiers == ("control",)
    assert parsed.key == "2"
    assert parsed.key_code == 19


@pytest.mark.parametrize("value", ["", "Command", "Command+Tab+2", "Command+do shell script"])
def test_invalid_shortcuts_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        parse_shortcut(value)


def test_execute_reports_missing_accessibility_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hotkey, "accessibility_is_trusted", lambda: False)
    ok, message = hotkey.execute_shortcut("Command+Tab")
    assert ok is False
    assert "辅助功能权限" in message

