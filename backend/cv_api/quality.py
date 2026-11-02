"""품질 검사기 — BR-CV-06(선명도·조도), BR-CV-07(신뢰도), BR-CV-21(겹침). 임계값은 settings (R5).

check_frame(img)            → blur / low_light / backlight
check_detections(boxes)     → low_confidence / occlusion
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

import cv2
import numpy as np

from .schemas import Warning, WarningCode
from .settings import Settings, get_settings

Box = Tuple[float, float, float, float, float]  # x1, y1, x2, y2, conf


def laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def check_frame(img_bgr: np.ndarray, s: Settings | None = None) -> List[Warning]:
    s = s or get_settings()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    out: List[Warning] = []
    lv = laplacian_variance(gray)
    if lv < s.BLUR_LAPLACIAN_MIN:
        out.append(Warning(code=WarningCode.blur, detail=f"영상 흐림 — 라플라시안 분산 {lv:.1f} < {s.BLUR_LAPLACIAN_MIN:g}"))
    mean = float(gray.mean())
    if mean < s.LOW_LIGHT_MEAN_MAX:
        out.append(Warning(code=WarningCode.low_light, detail=f"저조도 — 평균 밝기 {mean:.1f} < {s.LOW_LIGHT_MEAN_MAX:g}"))
    high = float((gray >= s.BACKLIGHT_HIGH_VALUE).mean())
    low = float((gray <= s.BACKLIGHT_LOW_VALUE).mean())
    if high >= s.BACKLIGHT_HIGH_RATIO and low >= s.BACKLIGHT_LOW_RATIO:
        out.append(Warning(code=WarningCode.backlight, detail=f"역광 — 밝음 {high:.0%} / 어두움 {low:.0%} 양극 분포"))
    return out


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / max(1e-9, area_a + area_b - inter)


def check_detections(boxes: Sequence[Box], s: Settings | None = None) -> Tuple[List[Warning], float]:
    """(경고 목록, 평균 신뢰도). 박스가 없으면 신뢰도 1.0 (E5: 사람이 없는 프레임은 정상 여유)."""
    s = s or get_settings()
    out: List[Warning] = []
    if not boxes:
        return out, 1.0
    mean_conf = float(sum(b[4] for b in boxes) / len(boxes))
    if mean_conf < s.CONFIDENCE_MIN:
        out.append(Warning(code=WarningCode.low_confidence, detail=f"평균 신뢰도 {mean_conf:.2f} < {s.CONFIDENCE_MIN:g}"))
    if len(boxes) >= 2:
        pairs = overlapped = 0
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                pairs += 1
                if iou(boxes[i], boxes[j]) > s.OCCLUSION_IOU:
                    overlapped += 1
        ratio = overlapped / pairs if pairs else 0.0
        if ratio > s.OCCLUSION_RATIO:
            out.append(Warning(code=WarningCode.occlusion, detail=f"승객 겹침 — 겹치는 박스 쌍 {ratio:.0%} > {s.OCCLUSION_RATIO:.0%}"))
    return out, mean_conf
