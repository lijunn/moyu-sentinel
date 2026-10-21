"""本人匹配和报警状态机测试。作者：LiJun。"""

from moyu_sentinel.detection import IntrusionStateMachine, SelfMatcher
from moyu_sentinel.geometry import DetectionBox


SELF = DetectionBox(0.25, 0.1, 0.75, 0.95, track_id=10)
OTHER = DetectionBox(0.72, 0.15, 0.95, 0.8, track_id=20)


def test_self_matcher_prefers_track_id() -> None:
    matcher = SelfMatcher()
    matcher.calibrate(SELF, now=0.0)
    index, visible = matcher.match([OTHER, SELF], now=0.2)
    assert index == 1
    assert visible is True


def test_self_matcher_reacquires_near_anchor() -> None:
    matcher = SelfMatcher()
    matcher.calibrate(SELF, now=0.0)
    moved_self = DetectionBox(0.27, 0.1, 0.77, 0.94, track_id=99)
    index, visible = matcher.match([moved_self], now=0.5)
    assert index == 0
    assert visible is True
    assert matcher.track_id == 99


def test_self_matcher_reports_lost_after_timeout() -> None:
    matcher = SelfMatcher(lost_timeout=2.0)
    matcher.calibrate(SELF, now=0.0)
    assert matcher.match([], now=1.0) == (None, True)
    assert matcher.match([], now=2.1) == (None, False)


def test_short_presence_does_not_trigger() -> None:
    machine = IntrusionStateMachine(hold_seconds=0.8, cooldown_seconds=15)
    assert machine.update(now=0.0, intruder_present=True, self_visible=True) is False
    assert machine.update(now=0.7, intruder_present=True, self_visible=True) is False
    assert machine.update(now=0.75, intruder_present=False, self_visible=True) is False


def test_sustained_presence_triggers_once() -> None:
    machine = IntrusionStateMachine(hold_seconds=0.8, cooldown_seconds=15)
    assert machine.update(now=0.0, intruder_present=True, self_visible=True) is False
    assert machine.update(now=0.8, intruder_present=True, self_visible=True) is True
    assert machine.update(now=2.0, intruder_present=True, self_visible=True) is False


def test_absence_and_cooldown_allow_new_trigger() -> None:
    machine = IntrusionStateMachine(hold_seconds=0.8, cooldown_seconds=10)
    machine.update(now=0.0, intruder_present=True, self_visible=True)
    assert machine.update(now=0.8, intruder_present=True, self_visible=True)
    machine.update(now=1.0, intruder_present=False, self_visible=True)
    machine.update(now=3.1, intruder_present=False, self_visible=True)
    machine.update(now=10.9, intruder_present=True, self_visible=True)
    assert machine.update(now=11.7, intruder_present=True, self_visible=True)


def test_missing_self_suppresses_alert() -> None:
    machine = IntrusionStateMachine(hold_seconds=0.5, cooldown_seconds=10)
    machine.update(now=0.0, intruder_present=True, self_visible=False)
    assert machine.update(now=1.0, intruder_present=True, self_visible=False) is False
