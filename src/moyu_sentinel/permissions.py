"""macOS 摄像头权限请求。

作者：LiJun
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class CameraPermissionRequester(QObject):
    """必须由主线程调用，避免 OpenCV 在工作线程请求权限失败。"""

    resolved = Signal(bool, str)

    def request(self) -> None:
        try:
            import AVFoundation
        except ImportError as error:
            self.resolved.emit(False, f"无法加载摄像头权限组件：{error}")
            return

        media_type = AVFoundation.AVMediaTypeVideo
        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(media_type)
        if status == AVFoundation.AVAuthorizationStatusAuthorized:
            self.resolved.emit(True, "摄像头权限已授权")
            return
        if status in (
            AVFoundation.AVAuthorizationStatusDenied,
            AVFoundation.AVAuthorizationStatusRestricted,
        ):
            self.resolved.emit(
                False,
                "摄像头权限被拒绝。请在“系统设置 → 隐私与安全性 → 摄像头”中允许终端或 Python。",
            )
            return

        def completion(granted: bool) -> None:
            if granted:
                self.resolved.emit(True, "摄像头权限已授权")
            else:
                self.resolved.emit(
                    False,
                    "摄像头权限被拒绝。请在系统设置中允许后重新启动。",
                )

        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            media_type, completion
        )
