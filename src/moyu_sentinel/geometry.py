"""人体框与危险区域的几何运算。

作者：LiJun
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .config import NormalizedRect


@dataclass(slots=True, frozen=True)
class DetectionBox:
    """归一化人体检测框。"""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0
    track_id: int | None = None

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def iou(self, other: "DetectionBox") -> float:
        left = max(self.x1, other.x1)
        top = max(self.y1, other.y1)
        right = min(self.x2, other.x2)
        bottom = min(self.y2, other.y2)
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0

    def overlap_ratio(self, rect: NormalizedRect) -> float:
        """返回人体框中落入目标区域的面积比例。"""

        right = rect.x + rect.width
        bottom = rect.y + rect.height
        overlap_width = max(0.0, min(self.x2, right) - max(self.x1, rect.x))
        overlap_height = max(0.0, min(self.y2, bottom) - max(self.y1, rect.y))
        overlap = overlap_width * overlap_height
        return overlap / self.area if self.area > 0 else 0.0

    def center_distance(self, other: "DetectionBox") -> float:
        first = self.center
        second = other.center
        return hypot(first[0] - second[0], first[1] - second[1])


def median_box(boxes: list[DetectionBox]) -> DetectionBox:
    """按每个坐标的中位数合成稳定的校准框。"""

    if not boxes:
        raise ValueError("至少需要一个检测框")

    def median(values: list[float]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2.0

    return DetectionBox(
        x1=median([item.x1 for item in boxes]),
        y1=median([item.y1 for item in boxes]),
        x2=median([item.x2 for item in boxes]),
        y2=median([item.y2 for item in boxes]),
        confidence=median([item.confidence for item in boxes]),
        track_id=boxes[-1].track_id,
    )

