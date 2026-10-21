"""摄像头采集、YOLO 推理与报警工作线程。

作者：LiJun
"""

from __future__ import annotations

import copy
import os
import threading
import time
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from .actions import trigger_alert
from .config import AppConfig
from .detection import IntrusionStateMachine, SelfMatcher
from .geometry import DetectionBox, median_box
from .paths import model_path


class MonitorThread(QThread):
    """把耗时的摄像头和推理工作放到 UI 线程之外。"""

    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    detail_changed = Signal(str)
    calibration_progress = Signal(int)
    calibration_finished = Signal(bool, str)
    fatal_error = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = copy.deepcopy(config)
        self._lock = threading.RLock()
        self._should_run = True
        self._monitoring_enabled = True
        self._calibration_requested = True
        self._alert_running = False

    def stop(self) -> None:
        with self._lock:
            self._should_run = False

    def set_monitoring(self, enabled: bool) -> None:
        with self._lock:
            self._monitoring_enabled = enabled

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self._config = copy.deepcopy(config.validate())

    def request_calibration(self) -> None:
        with self._lock:
            self._calibration_requested = True

    def _snapshot(self) -> tuple[AppConfig, bool, bool, bool]:
        with self._lock:
            requested = self._calibration_requested
            self._calibration_requested = False
            return (
                copy.deepcopy(self._config),
                self._monitoring_enabled,
                requested,
                self._should_run,
            )

    @staticmethod
    def _extract_boxes(result: Any, width: int, height: int) -> list[DetectionBox]:
        boxes: list[DetectionBox] = []
        if result is None or result.boxes is None:
            return boxes
        coordinates = result.boxes.xyxy.detach().cpu().tolist()
        confidences = result.boxes.conf.detach().cpu().tolist()
        raw_ids = result.boxes.id
        ids = raw_ids.detach().cpu().tolist() if raw_ids is not None else [None] * len(coordinates)
        for coordinate, confidence, track_id in zip(coordinates, confidences, ids):
            x1, y1, x2, y2 = coordinate
            boxes.append(
                DetectionBox(
                    x1=max(0.0, min(1.0, x1 / width)),
                    y1=max(0.0, min(1.0, y1 / height)),
                    x2=max(0.0, min(1.0, x2 / width)),
                    y2=max(0.0, min(1.0, y2 / height)),
                    confidence=float(confidence),
                    track_id=int(track_id) if track_id is not None else None,
                )
            )
        return boxes

    @staticmethod
    def _central_candidate(detections: list[DetectionBox]) -> DetectionBox | None:
        """校准时选择最靠近画面中央且面积合理的主体。"""

        candidates: list[tuple[float, DetectionBox]] = []
        for item in detections:
            center_x, center_y = item.center
            distance = ((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) ** 0.5
            if distance <= 0.35:
                candidates.append((distance - item.area * 0.2, item))
        return min(candidates, key=lambda pair: pair[0])[1] if candidates else None

    @staticmethod
    def _draw_detections(
        frame: Any,
        detections: list[DetectionBox],
        self_index: int | None,
        dangerous_indices: set[int],
    ) -> Any:
        import cv2

        height, width = frame.shape[:2]
        output = frame.copy()
        for index, item in enumerate(detections):
            if index == self_index:
                color, label = (60, 190, 90), "SELF"
            elif index in dangerous_indices:
                color, label = (50, 60, 230), "DANGER"
            else:
                color, label = (20, 170, 240), "PERSON"
            first = (int(item.x1 * width), int(item.y1 * height))
            second = (int(item.x2 * width), int(item.y2 * height))
            cv2.rectangle(output, first, second, color, 2)
            cv2.putText(
                output,
                f"{label} {item.confidence:.2f}",
                (first[0], max(20, first[1] - 7)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
        return output

    def _perform_alert(self, shortcut: str) -> None:
        try:
            ok, message = trigger_alert(shortcut)
            self.detail_changed.emit(message if ok else f"自动动作失败：{message}")
        finally:
            with self._lock:
                self._alert_running = False

    def _start_alert(self, shortcut: str) -> None:
        with self._lock:
            if self._alert_running:
                return
            self._alert_running = True
        threading.Thread(
            target=self._perform_alert,
            args=(shortcut,),
            daemon=True,
            name="MoyuSentinelAlert",
        ).start()

    def run(self) -> None:  # noqa: C901 - 实时循环集中在一个线程中更容易可靠释放摄像头
        # 摄像头权限已在 UI 主线程请求；禁止 OpenCV 在本线程重复请求。
        os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
        try:
            import cv2
            import torch
            from ultralytics import YOLO
        except ImportError as error:
            self.fatal_error.emit(f"依赖加载失败：{error}")
            return

        weights = model_path()
        self.status_changed.emit("正在加载 YOLO 模型，首次运行可能需要下载…")
        try:
            model = YOLO(str(weights))
        except Exception as error:  # 模型下载与解析可能抛出多种第三方异常
            self.fatal_error.emit(f"YOLO 模型加载失败：{error}")
            return

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.detail_changed.emit(f"推理设备：{device.upper()}")
        capture = None
        opened_camera_index: int | None = None
        matcher = SelfMatcher(lost_timeout=2.0)
        state = IntrusionStateMachine()
        calibrating = False
        calibration_started_at: float | None = None
        calibration_samples: list[DetectionBox] = []
        latest_boxes: list[DetectionBox] = []
        latest_self_index: int | None = None
        latest_dangerous: set[int] = set()
        latest_self_visible = False
        last_inference_at = 0.0

        try:
            while True:
                config, monitoring_enabled, calibration_requested, should_run = self._snapshot()
                if not should_run or self.isInterruptionRequested():
                    break

                if capture is None or opened_camera_index != config.camera_index:
                    if capture is not None:
                        capture.release()
                    capture = cv2.VideoCapture(config.camera_index, cv2.CAP_AVFOUNDATION)
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    opened_camera_index = config.camera_index
                    matcher.clear()
                    calibration_requested = True
                    if not capture.isOpened():
                        self.status_changed.emit("无法打开摄像头，请检查摄像头权限")
                        self.msleep(1500)
                        capture.release()
                        capture = None
                        continue

                if calibration_requested:
                    calibrating = True
                    calibration_started_at = None
                    calibration_samples.clear()
                    matcher.clear()
                    state.reset()
                    self.calibration_progress.emit(0)
                    self.status_changed.emit("请坐在画面中央，正在校准本人…")

                success, frame = capture.read()
                if not success or frame is None:
                    self.status_changed.emit("摄像头读取失败，正在重试…")
                    self.msleep(100)
                    continue

                now = time.monotonic()
                if now - last_inference_at >= 0.2:
                    last_inference_at = now
                    try:
                        results = model.track(
                            frame,
                            persist=True,
                            classes=[0],
                            conf=config.confidence,
                            verbose=False,
                            device=device,
                            tracker="bytetrack.yaml",
                        )
                    except Exception as error:
                        if device == "mps":
                            device = "cpu"
                            self.detail_changed.emit(f"MPS 推理失败，已回退 CPU：{error}")
                            continue
                        self.status_changed.emit(f"推理失败：{error}")
                        self.msleep(200)
                        continue

                    height, width = frame.shape[:2]
                    latest_boxes = self._extract_boxes(
                        results[0] if results else None, width, height
                    )

                    if calibrating:
                        candidate = self._central_candidate(latest_boxes)
                        if candidate is not None:
                            if calibration_started_at is None:
                                calibration_started_at = now
                            calibration_samples.append(candidate)
                            elapsed = now - calibration_started_at
                            self.calibration_progress.emit(min(100, int(elapsed / 3.0 * 100)))
                            if elapsed >= 3.0 and len(calibration_samples) >= 5:
                                anchor = median_box(calibration_samples)
                                matcher.calibrate(anchor, now)
                                calibrating = False
                                self.calibration_progress.emit(100)
                                self.calibration_finished.emit(True, "本人校准完成")
                        else:
                            calibration_started_at = None
                            calibration_samples.clear()
                            self.calibration_progress.emit(0)

                    latest_self_index, latest_self_visible = matcher.match(latest_boxes, now)
                    latest_dangerous = {
                        index
                        for index, item in enumerate(latest_boxes)
                        if index != latest_self_index
                        and item.overlap_ratio(config.danger_zone) >= 0.2
                    }

                    state.configure(config.hold_seconds, config.cooldown_seconds)
                    if not monitoring_enabled or calibrating:
                        state.reset()
                    should_alert = state.update(
                        now=now,
                        intruder_present=bool(latest_dangerous),
                        self_visible=latest_self_visible and not calibrating,
                    )
                    if should_alert:
                        self.status_changed.emit("检测到危险区域有人")
                        self._start_alert(config.shortcut)
                    elif calibrating:
                        pass
                    elif not monitoring_enabled:
                        self.status_changed.emit("监控已暂停，仅显示画面")
                    elif not latest_self_visible:
                        self.status_changed.emit("本人已丢失，自动动作已暂停，请重新校准")
                    elif latest_dangerous:
                        self.status_changed.emit("检测到人员，正在确认持续时间…")
                    else:
                        self.status_changed.emit("监控中：未发现危险区域人员")

                rendered = self._draw_detections(
                    frame, latest_boxes, latest_self_index, latest_dangerous
                )
                rgb = cv2.cvtColor(rendered, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb.shape
                image = QImage(
                    rgb.data,
                    width,
                    height,
                    channels * width,
                    QImage.Format.Format_RGB888,
                ).copy()
                self.frame_ready.emit(image)
                self.msleep(15)
        finally:
            if capture is not None:
                capture.release()
