"""MoyuSentinel 应用入口。

作者：LiJun
"""

from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .config import load_config
from .window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("MoyuSentinel")
    application.setOrganizationName("LiJun")
    window = MainWindow(load_config())
    window.show()
    # Qt 事件循环需要周期性返回 Python，才能及时处理终端的 Control-C。
    signal.signal(signal.SIGINT, lambda *_args: window.close())
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    application._moyu_sentinel_signal_timer = signal_timer  # type: ignore[attr-defined]
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())

