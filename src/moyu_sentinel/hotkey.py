"""macOS 快捷键白名单解析与 Quartz 原生执行。

作者：LiJun
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass


MODIFIER_ALIASES = {
    "command": "command", "cmd": "command", "⌘": "command",
    "control": "control", "ctrl": "control", "⌃": "control",
    "option": "option", "alt": "option", "⌥": "option",
    "shift": "shift", "⇧": "shift",
}

# macOS 虚拟键码与键盘布局无关，适合发送系统级快捷键。
KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5,
    "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "9": 25, "7": 26, "8": 28, "0": 29,
    "o": 31, "u": 32, "i": 34, "p": 35,
    "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "tab": 48, "space": 49, "enter": 36, "return": 36,
    "escape": 53, "esc": 53, "left": 123, "right": 124,
    "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118,
    "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

MODIFIER_KEY_CODES = {
    "command": 55,
    "shift": 56,
    "option": 58,
    "control": 59,
}


@dataclass(slots=True, frozen=True)
class ParsedShortcut:
    modifiers: tuple[str, ...]
    key: str
    key_code: int


def parse_shortcut(value: str) -> ParsedShortcut:
    """解析类似 Command+Tab 的组合键，拒绝所有非白名单内容。"""

    parts = [part.strip() for part in value.split("+") if part.strip()]
    if not parts:
        raise ValueError("快捷键不能为空")

    modifiers: list[str] = []
    key: str | None = None
    for raw_part in parts:
        normalized = raw_part.lower()
        modifier = MODIFIER_ALIASES.get(normalized)
        if modifier:
            if modifier not in modifiers:
                modifiers.append(modifier)
            continue
        if key is not None:
            raise ValueError("快捷键只能包含一个主按键")
        if normalized not in KEY_CODES:
            raise ValueError(f"不支持的按键：{raw_part}")
        key = normalized

    if key is None:
        raise ValueError("快捷键缺少主按键")
    return ParsedShortcut(tuple(modifiers), key, KEY_CODES[key])


def accessibility_is_trusted() -> bool:
    """直接查询当前进程是否具有辅助功能权限。"""

    framework_path = (
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )
    try:
        application_services = ctypes.cdll.LoadLibrary(framework_path)
        function = application_services.AXIsProcessTrusted
        function.argtypes = []
        function.restype = ctypes.c_bool
        return bool(function())
    except (AttributeError, OSError):
        return False


def _post_shortcut(shortcut: ParsedShortcut) -> None:
    """按下修饰键、主按键，再按相反顺序释放修饰键。"""

    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskAlternate,
        kCGEventFlagMaskCommand,
        kCGEventFlagMaskControl,
        kCGEventFlagMaskShift,
        kCGHIDEventTap,
    )

    flag_by_modifier = {
        "command": kCGEventFlagMaskCommand,
        "control": kCGEventFlagMaskControl,
        "option": kCGEventFlagMaskAlternate,
        "shift": kCGEventFlagMaskShift,
    }
    flags = 0

    def post(key_code: int, pressed: bool, event_flags: int) -> None:
        event = CGEventCreateKeyboardEvent(None, key_code, pressed)
        if event is None:
            raise RuntimeError("无法创建 macOS 键盘事件")
        CGEventSetFlags(event, event_flags)
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(0.015)

    for modifier in shortcut.modifiers:
        flags |= flag_by_modifier[modifier]
        post(MODIFIER_KEY_CODES[modifier], True, flags)

    post(shortcut.key_code, True, flags)
    post(shortcut.key_code, False, flags)

    for modifier in reversed(shortcut.modifiers):
        flags &= ~flag_by_modifier[modifier]
        post(MODIFIER_KEY_CODES[modifier], False, flags)


def execute_shortcut(value: str) -> tuple[bool, str]:
    """通过 Quartz 执行快捷键，不再依赖 System Events 自动化权限。"""

    try:
        shortcut = parse_shortcut(value)
    except ValueError as error:
        return False, str(error)

    if not accessibility_is_trusted():
        return (
            False,
            "MoyuSentinel 尚未获得辅助功能权限。请在“系统设置 → 隐私与安全性 → "
            "辅助功能”中允许终端，然后彻底退出并重新打开终端和 MoyuSentinel。",
        )

    try:
        _post_shortcut(shortcut)
    except (ImportError, OSError, RuntimeError) as error:
        return False, f"Quartz 快捷键执行失败：{error}"
    return True, "快捷键执行成功（Quartz）"
