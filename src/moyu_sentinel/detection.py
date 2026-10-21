"""本人匹配与报警状态机。

作者：LiJun
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import DetectionBox


class SelfMatcher:
    """结合跟踪编号、历史位置和校准区域持续识别本人。"""

    def __init__(self, lost_timeout: float = 2.0) -> None:
        self.lost_timeout = lost_timeout
        self.anchor: DetectionBox | None = None
        self.current: DetectionBox | None = None
        self.track_id: int | None = None
        self.last_seen_at: float | None = None

    def calibrate(self, anchor: DetectionBox, now: float) -> None:
        self.anchor = anchor
        self.current = anchor
        self.track_id = anchor.track_id
        self.last_seen_at = now

    def clear(self) -> None:
        self.anchor = None
        self.current = None
        self.track_id = None
        self.last_seen_at = None

    def _score(self, candidate: DetectionBox) -> float:
        if self.anchor is None:
            return 0.0
        history_iou = candidate.iou(self.current) if self.current else 0.0
        anchor_iou = candidate.iou(self.anchor)
        if self.anchor.area and candidate.area:
            area_similarity = min(self.anchor.area, candidate.area) / max(
                self.anchor.area, candidate.area
            )
        else:
            area_similarity = 0.0
        return history_iou * 0.6 + anchor_iou * 0.25 + area_similarity * 0.15

    def match(
        self, detections: list[DetectionBox], now: float
    ) -> tuple[int | None, bool]:
        """返回本人在检测列表中的下标，以及本人当前是否可靠可见。"""

        if self.anchor is None:
            return None, False

        if self.track_id is not None:
            for index, candidate in enumerate(detections):
                if candidate.track_id == self.track_id:
                    self.current = candidate
                    self.last_seen_at = now
                    return index, True

        scored = [(self._score(item), index) for index, item in enumerate(detections)]
        if scored:
            score, index = max(scored)
            candidate = detections[index]
            # 跟踪编号丢失后，只在位置和体型足够接近时重新绑定。
            if score >= 0.28 or candidate.iou(self.anchor) >= 0.3:
                self.current = candidate
                self.track_id = candidate.track_id
                self.last_seen_at = now
                return index, True

        visible = (
            self.last_seen_at is not None and now - self.last_seen_at <= self.lost_timeout
        )
        return None, visible


@dataclass(slots=True)
class IntrusionStateMachine:
    """把逐帧检测结果转换为一次性的报警事件。"""

    hold_seconds: float = 0.8
    cooldown_seconds: float = 15.0
    absence_reset_seconds: float = 2.0
    pending_since: float | None = None
    absence_since: float | None = None
    last_trigger_at: float | None = None
    active_triggered: bool = False

    def configure(self, hold_seconds: float, cooldown_seconds: float) -> None:
        self.hold_seconds = hold_seconds
        self.cooldown_seconds = cooldown_seconds

    def reset(self) -> None:
        self.pending_since = None
        self.absence_since = None
        self.active_triggered = False

    def update(self, *, now: float, intruder_present: bool, self_visible: bool) -> bool:
        if not self_visible:
            self.pending_since = None
            return False

        if intruder_present:
            self.absence_since = None
            if self.active_triggered:
                return False
            if self.pending_since is None:
                self.pending_since = now
                return False
            # 单调时钟仍是浮点数，加入极小容差避免 0.8 被表示成 0.799999…。
            held_long_enough = now - self.pending_since + 1e-9 >= self.hold_seconds
            cooldown_ready = (
                self.last_trigger_at is None
                or now - self.last_trigger_at >= self.cooldown_seconds
            )
            if held_long_enough and cooldown_ready:
                self.active_triggered = True
                self.last_trigger_at = now
                return True
            return False

        self.pending_since = None
        if self.active_triggered:
            if self.absence_since is None:
                self.absence_since = now
            elif now - self.absence_since >= self.absence_reset_seconds:
                self.active_triggered = False
                self.absence_since = None
        return False

