"""应用路径定义。

作者：LiJun
"""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """返回项目根目录，便于双击启动器和命令行使用同一份数据。"""

    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """返回本地数据目录；测试时可通过环境变量覆盖。"""

    # 新变量优先；保留旧变量兼容升级前的本地启动脚本。
    override = os.environ.get("MOYU_SENTINEL_DATA_DIR") or os.environ.get(
        "BEHIND_GUARD_DATA_DIR"
    )
    path = Path(override).expanduser() if override else project_root() / ".data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_path() -> Path:
    """返回 YOLO 模型文件位置。"""

    path = data_dir() / "models" / "yolo11n.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
