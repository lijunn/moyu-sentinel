"""报警后的本地系统动作。

作者：LiJun
"""

from __future__ import annotations

import subprocess
import time

from .hotkey import execute_shortcut


def send_notification(message: str) -> tuple[bool, str]:
    """使用参数化的 osascript 调用显示通知，避免 shell 注入。"""

    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "MoyuSentinel"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    if result.returncode != 0:
        return False, result.stderr.strip() or "通知发送失败"
    return True, "通知已发送"


def trigger_alert(shortcut: str) -> tuple[bool, str]:
    """先通知，再稍作等待并执行用户配置的快捷键。"""

    notification_ok, notification_message = send_notification("检测到身后危险区域有人")
    time.sleep(0.25)
    shortcut_ok, shortcut_message = execute_shortcut(shortcut)
    if notification_ok and shortcut_ok:
        return True, "已通知并执行快捷键"
    details = "；".join(
        message
        for ok, message in (
            (notification_ok, notification_message),
            (shortcut_ok, shortcut_message),
        )
        if not ok
    )
    return False, details
