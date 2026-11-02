"""T024 — 품질 검사 (BR-CV-06·07·21, SC-06): 합성 프레임에서 blur·low_light·backlight·low_confidence·occlusion 검출."""
import cv2
import numpy as np

from cv_api import quality
from cv_api.schemas import WarningCode
from cv_api.settings import get_settings
from tests.helpers import make_frame


def _decode(b: bytes):
    return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)


def test_sharp_frame_no_quality_warning():
    assert quality.check_frame(_decode(make_frame())) == []


def test_blur_detected_100pct():
    for seed in range(5):
        img = _decode(make_frame(blur=True))
        codes = {w.code for w in quality.check_frame(img)}
        assert WarningCode.blur in codes


def test_low_light_detected():
    codes = {w.code for w in quality.check_frame(_decode(make_frame(dark=True)))}
    assert WarningCode.low_light in codes


def test_backlight_detected():
    img = np.zeros((480, 640, 3), np.uint8)
    img[:, :200] = 255          # 강한 광원 31%
    img[:, 200:] = 10           # 어두운 나머지
    img = np.clip(img.astype(np.int16) + np.random.default_rng(0).integers(-2, 3, img.shape, dtype=np.int16), 0, 255).astype(np.uint8)
    codes = {w.code for w in quality.check_frame(img)}
    assert WarningCode.backlight in codes


def test_low_confidence_and_occlusion():
    boxes = [(0, 0, 100, 200, 0.4), (10, 5, 110, 205, 0.5), (300, 0, 400, 200, 0.55)]
    w, mean = quality.check_detections(boxes)
    codes = {x.code for x in w}
    assert WarningCode.low_confidence in codes and mean < get_settings().CONFIDENCE_MIN
    assert WarningCode.occlusion in codes      # 3쌍 중 1쌍 겹침 = 33% > 30%


def test_thresholds_follow_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "BLUR_LAPLACIAN_MIN", 0.0)
    assert WarningCode.blur not in {w.code for w in quality.check_frame(_decode(make_frame(blur=True)), s)}
