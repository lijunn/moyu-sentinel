"""几何运算测试。作者：LiJun。"""

from moyu_sentinel.config import NormalizedRect
from moyu_sentinel.geometry import DetectionBox, median_box


def test_overlap_ratio() -> None:
    person = DetectionBox(0.0, 0.0, 0.5, 1.0)
    zone = NormalizedRect(0.25, 0.0, 0.75, 1.0)
    assert person.overlap_ratio(zone) == 0.5


def test_iou() -> None:
    first = DetectionBox(0.0, 0.0, 0.5, 0.5)
    second = DetectionBox(0.25, 0.25, 0.75, 0.75)
    assert round(first.iou(second), 4) == 0.1429


def test_median_box_rejects_jitter() -> None:
    result = median_box(
        [
            DetectionBox(0.2, 0.1, 0.7, 0.9, track_id=1),
            DetectionBox(0.21, 0.11, 0.71, 0.91, track_id=1),
            DetectionBox(0.8, 0.8, 1.0, 1.0, track_id=9),
        ]
    )
    assert result.x1 == 0.21
    assert result.y1 == 0.11

