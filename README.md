# MoyuSentinel（摸鱼哨兵）

作者：LiJun

MoyuSentinel 是一个仅在本机运行的 macOS 老板接近预警工具。它使用内置摄像头和 YOLO11n 识别画面中的人员，忽略校准后的本人；当其他人在危险区域内持续出现时，程序会发送系统通知并执行配置的快捷键。

> Work smarter. Look busy. 👀

程序不会录像、不会保存截图、不会保存人脸特征，也不会上传摄像头画面。首次运行需要联网安装依赖和下载 YOLO 模型，模型下载完成后可以离线使用。

## 系统要求

- macOS 13 或更高版本
- Apple Silicon Mac
- 已安装 [`uv`](https://docs.astral.sh/uv/)
- 可用的内置或 USB 摄像头

## 启动

克隆项目：

```bash
git clone https://github.com/lijunn/moyu-sentinel.git
cd moyu-sentinel
```

先赋予启动器执行权限（仅第一次需要）：

```bash
chmod +x run.command
```

随后可在 Finder 中双击 `run.command`，也可以在终端运行：

```bash
uv run moyu-sentinel
```

首次运行会创建 `.venv` 和 `.data`：

- `.data/config.json`：检测参数、危险区域和快捷键。
- `.data/models/yolo11n.pt`：本地 YOLO 模型。

## 首次设置

1. macOS 请求摄像头权限时选择“允许”。如果没有弹窗，请打开“系统设置 → 隐私与安全性 → 摄像头”，允许终端或 Python 使用摄像头。
2. 坐在画面中央并保持正常姿势，等待 3 秒完成本人校准。
3. 在视频画面中按住鼠标左键拖拽，划定黄色危险区域。
4. 点击“测试快捷键”。如系统拒绝执行，打开“系统设置 → 隐私与安全性 → 辅助功能”，允许终端控制电脑，然后彻底退出并重新打开终端与 MoyuSentinel。

默认快捷键为 `Command+Tab`，作用是切换到上一个应用，不是切换 macOS 桌面空间。需要切到桌面 2 时，可以把快捷键改成 `Control+2`，并确认“系统设置 → 键盘 → 键盘快捷键 → 调度中心”中已启用该组合键。

支持的修饰键为 `Command`、`Control`、`Option`、`Shift`，主按键支持单个字母、数字、方向键、Tab、Enter、Space、Escape 和 F1～F12。例如：

- `Command+Tab`
- `Control+2`
- `Command+Shift+H`

程序会在主界面启动阶段使用 macOS AVFoundation 请求摄像头权限；授权完成后才启动后台识别线程，避免 OpenCV 无法从工作线程弹出首次授权窗口的问题。

快捷键通过 macOS Quartz 原生事件执行，不使用 AppleScript 或 System Events，因此不需要“自动化”权限；macOS 强制要求的“辅助功能”权限仍然必须由用户手动授予。

## 使用说明

- 绿色 `SELF` 框表示本人。
- 黄色 `PERSON` 框表示危险区域之外的其他人。
- 红色 `DANGER` 框表示进入危险区域的其他人。
- 本人连续丢失超过 2 秒时，程序会暂停自动动作，避免把本人误认为入侵者。
- 同一人员持续停留只触发一次；其离开至少 2 秒并且冷却时间结束后，才会再次触发。
- 调整摄像头位置或座位后，请点击“重新校准本人”。

## 测试

```bash
uv run pytest
```

核心逻辑测试不需要打开摄像头；摄像头授权、通知和快捷键需要在 Mac 上手工验收。

## 隐私与用途

MoyuSentinel 不进行人脸识别，无法判断画面中的人是否真的是老板。它只检测校准本人以外的其他人员。本项目仅供个人隐私提醒、娱乐和技术研究，请遵守所在地法律并尊重他人隐私。

## 许可证

本项目采用 [MIT License](LICENSE)。
