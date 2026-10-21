"""MoyuSentinel 主窗口。

作者：LiJun
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, NormalizedRect, save_config
from .hotkey import execute_shortcut, parse_shortcut
from .monitor import MonitorThread
from .permissions import CameraPermissionRequester
from .video_widget import VideoWidget


class MainWindow(QMainWindow):
    """显示实时画面，并集中管理全部用户设置。"""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config.validate()
        self.monitoring_enabled = True
        self.setWindowTitle("MoyuSentinel · 摸鱼哨兵")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        self.video = VideoWidget()
        self.video.set_danger_zone(self.config.danger_zone)
        self.video.danger_zone_changed.connect(self._danger_zone_changed)

        self.status_label = QLabel("正在启动…")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("statusLabel")
        self.detail_label = QLabel("所有画面仅在内存中处理，不会保存或上传。")
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("detailLabel")
        self.calibration_bar = QProgressBar()
        self.calibration_bar.setRange(0, 100)
        self.calibration_bar.setValue(0)
        self.calibration_bar.setFormat("本人校准 %p%")

        self.toggle_button = QPushButton("暂停监控")
        self.toggle_button.clicked.connect(self._toggle_monitoring)
        self.calibrate_button = QPushButton("重新校准本人")
        self.calibrate_button.clicked.connect(self._request_calibration)
        self.full_zone_button = QPushButton("危险区域设为全画面")
        self.full_zone_button.clicked.connect(self._reset_danger_zone)

        button_row = QHBoxLayout()
        button_row.addWidget(self.toggle_button)
        button_row.addWidget(self.calibrate_button)
        button_row.addWidget(self.full_zone_button)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.video, 1)
        left_layout.addLayout(button_row)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.detail_label)

        self.camera_spin = QSpinBox()
        self.camera_spin.setRange(0, 8)
        self.camera_spin.setValue(self.config.camera_index)
        self.camera_spin.valueChanged.connect(self._settings_changed)

        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.10, 0.95)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setValue(self.config.confidence)
        self.confidence_spin.valueChanged.connect(self._settings_changed)

        self.hold_spin = QDoubleSpinBox()
        self.hold_spin.setRange(0.5, 1.0)
        self.hold_spin.setSingleStep(0.1)
        self.hold_spin.setSuffix(" 秒")
        self.hold_spin.setValue(self.config.hold_seconds)
        self.hold_spin.valueChanged.connect(self._settings_changed)

        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(10.0, 30.0)
        self.cooldown_spin.setSingleStep(1.0)
        self.cooldown_spin.setSuffix(" 秒")
        self.cooldown_spin.setValue(self.config.cooldown_seconds)
        self.cooldown_spin.valueChanged.connect(self._settings_changed)

        self.shortcut_edit = QLineEdit(self.config.shortcut)
        self.shortcut_edit.setPlaceholderText("例如 Command+Tab 或 Control+2")
        self.shortcut_edit.editingFinished.connect(self._shortcut_changed)
        self.test_shortcut_button = QPushButton("测试快捷键")
        self.test_shortcut_button.clicked.connect(self._test_shortcut)

        settings_form = QFormLayout()
        settings_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        settings_form.addRow("摄像头编号", self.camera_spin)
        settings_form.addRow("检测置信度", self.confidence_spin)
        settings_form.addRow("持续确认时间", self.hold_spin)
        settings_form.addRow("报警冷却时间", self.cooldown_spin)
        settings_form.addRow("触发快捷键", self.shortcut_edit)
        settings_form.addRow("", self.test_shortcut_button)

        help_text = QLabel(
            "使用步骤\n\n"
            "1. 允许摄像头权限。\n"
            "2. 坐在画面中央等待 3 秒校准。\n"
            "3. 在画面上拖拽黄色危险区域。\n"
            "4. 使用“测试快捷键”检查辅助功能权限。\n\n"
            "默认 Command+Tab 会切换到上一个应用，并非切换桌面空间。"
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("helpText")

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        title = QLabel("身后守卫")
        title.setObjectName("titleLabel")
        subtitle = QLabel("本地人体检测 · 不保存画面")
        subtitle.setObjectName("subtitleLabel")
        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addSpacing(12)
        panel_layout.addWidget(self.calibration_bar)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        panel_layout.addWidget(separator)
        panel_layout.addLayout(settings_form)
        panel_layout.addSpacing(14)
        panel_layout.addWidget(help_text)
        panel_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(330)
        scroll.setWidget(panel)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.addLayout(left_layout, 1)
        root_layout.addWidget(scroll)
        self.setCentralWidget(root)
        self.setStyleSheet(self._style_sheet())

        self.worker = MonitorThread(self.config)
        self.worker.frame_ready.connect(self.video.set_image)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.detail_changed.connect(self.detail_label.setText)
        self.worker.calibration_progress.connect(self.calibration_bar.setValue)
        self.worker.calibration_finished.connect(self._calibration_finished)
        self.worker.fatal_error.connect(self._fatal_error)
        self.permission_requester = CameraPermissionRequester(self)
        self.permission_requester.resolved.connect(self._camera_permission_resolved)
        self.permission_requester.request()

    @staticmethod
    def _style_sheet() -> str:
        return """
        QMainWindow, QWidget { background: #171a20; color: #e9edf2; }
        QScrollArea { border: 1px solid #303640; border-radius: 10px; }
        QLabel#titleLabel { font-size: 26px; font-weight: 700; }
        QLabel#subtitleLabel { color: #9ea8b7; font-size: 13px; }
        QLabel#statusLabel { background: #222832; border-radius: 8px; padding: 10px; font-weight: 600; }
        QLabel#detailLabel, QLabel#helpText { color: #aeb7c5; padding: 4px; }
        QPushButton { background: #2d6cdf; border: none; border-radius: 7px; padding: 9px 12px; font-weight: 600; }
        QPushButton:hover { background: #3d7bea; }
        QPushButton:pressed { background: #245bbf; }
        QLineEdit, QSpinBox, QDoubleSpinBox { background: #222832; border: 1px solid #3a424f; border-radius: 6px; padding: 6px; }
        QProgressBar { background: #222832; border: none; border-radius: 6px; text-align: center; }
        QProgressBar::chunk { background: #39a96b; border-radius: 6px; }
        """

    def _persist_and_apply(self) -> None:
        self.config = AppConfig(
            camera_index=self.camera_spin.value(),
            confidence=self.confidence_spin.value(),
            hold_seconds=self.hold_spin.value(),
            cooldown_seconds=self.cooldown_spin.value(),
            danger_zone=self.config.danger_zone,
            shortcut=self.config.shortcut,
        ).validate()
        save_config(self.config)
        self.worker.update_config(self.config)

    def _settings_changed(self, _value: object = None) -> None:
        self._persist_and_apply()

    def _shortcut_changed(self) -> None:
        value = self.shortcut_edit.text().strip()
        try:
            parse_shortcut(value)
        except ValueError as error:
            self.shortcut_edit.setStyleSheet("border: 1px solid #e85d5d;")
            self.detail_label.setText(f"快捷键无效：{error}")
            return
        self.shortcut_edit.setStyleSheet("")
        self.config.shortcut = value
        self._persist_and_apply()
        self.detail_label.setText(f"快捷键已保存：{value}")

    def _danger_zone_changed(self, zone: NormalizedRect) -> None:
        self.config.danger_zone = zone
        self._persist_and_apply()
        self.detail_label.setText("危险区域已更新")

    def _reset_danger_zone(self) -> None:
        zone = NormalizedRect()
        self.video.set_danger_zone(zone)
        self._danger_zone_changed(zone)

    def _toggle_monitoring(self) -> None:
        self.monitoring_enabled = not self.monitoring_enabled
        self.worker.set_monitoring(self.monitoring_enabled)
        self.toggle_button.setText("暂停监控" if self.monitoring_enabled else "恢复监控")
        if not self.monitoring_enabled:
            self.status_label.setText("监控已暂停，仅显示画面")

    def _request_calibration(self) -> None:
        self.calibrate_button.setEnabled(False)
        self.worker.request_calibration()

    def _calibration_finished(self, success: bool, message: str) -> None:
        self.calibrate_button.setEnabled(True)
        self.detail_label.setText(message)
        if not success:
            QMessageBox.warning(self, "校准失败", message)

    def _test_shortcut(self) -> None:
        value = self.shortcut_edit.text().strip()
        try:
            parse_shortcut(value)
        except ValueError as error:
            QMessageBox.warning(self, "快捷键无效", str(error))
            return
        QMessageBox.information(
            self,
            "即将测试",
            f"点击“好”后将执行 {value}。如果失败，请在系统设置中授予辅助功能权限。",
        )
        ok, message = execute_shortcut(value)
        if not ok:
            QMessageBox.warning(self, "执行失败", message)

    def _fatal_error(self, message: str) -> None:
        self.status_label.setText(message)
        QMessageBox.critical(self, "MoyuSentinel 无法启动", message)

    def _camera_permission_resolved(self, granted: bool, message: str) -> None:
        self.detail_label.setText(message)
        if granted:
            if not self.worker.isRunning():
                self.worker.start()
            return
        self.status_label.setText("摄像头不可用，监控尚未启动")
        QMessageBox.warning(self, "需要摄像头权限", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.worker.stop()
        if self.worker.isRunning() and not self.worker.wait(4000):
            self.worker.requestInterruption()
            self.status_label.setText("正在安全关闭摄像头和识别线程…")
            QTimer.singleShot(500, self.close)
            event.ignore()
            return
        event.accept()

