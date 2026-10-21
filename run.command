#!/bin/zsh
# 作者：LiJun
# 双击本文件即可在项目目录中启动 MoyuSentinel。

set -e
SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  osascript -e 'display dialog "未找到 uv。请先安装 uv，再重新双击启动。" buttons {"好"} default button "好" with icon stop'
  exit 1
fi

exec uv run moyu-sentinel

