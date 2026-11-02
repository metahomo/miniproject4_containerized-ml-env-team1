"""규격 변환 — 웹 백엔드(9524)가 웹 화면에서 받은 사진·영상을 진단 API 규격(FR-02, R4)에 맞춘다.

진단 API(9544)는 규격 밖을 반려(BR-CV-11)하는 계약을 그대로 지키고, 변환은 그 앞단인 웹 백엔드에서만 한다.

- 사진: 디코드(JPEG·PNG·WebP·BMP·TIFF·GIF 첫 장·HEIC) → EXIF 회전 반영 → 긴 변이 NORMALIZE_MAX_SIDE 를 넘으면 축소 → JPEG.
  이미 규격 안(JPEG·PNG, 해상도·용량 범위, 회전 정보 없음)이면 원본 그대로 보낸다.
- **키우지 않는다**: 짧은 변이 IMAGE_MIN_SIDE 미만이면 반려한다. 확대는 없는 정보를 만들어 검출을 부정확하게 하면서 결과는 정상처럼 보이게 한다.
- 영상: FFmpeg(OpenCV) 로 지정 시각의 프레임을 뽑아 사진과 같은 규칙으로 변환한다.
  OpenCV 는 파일 경로만 읽으므로 요청 처리 동안만 임시 파일에 두고 끝나면 지운다(FR-11 — 원본 미보관).
"""
from __future__ import annotations

import io
import os
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Iterator, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

from .gates import GateBlocked
from .settings import Settings, get_settings

try:  # 휴대폰 HEIC — 없으면 HEIC 만 '지원 형식 아님'으로 반려
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

Image.MAX_IMAGE_PIXELS = 100_000_000   # 압축 폭탄 방지 (1억 화소)


@dataclass
class Normalization:
    applied: bool
    source: dict                      # 원본: format, width, height, bytes
    output: dict                      # 보낸 것: format, width, height, bytes
    steps: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["from"] = d.pop("source")
        d["to"] = d.pop("output")
        return d


def _reject(code: str, why: str, s: Settings) -> GateBlocked:
    spec = {"min_side": s.IMAGE_MIN_SIDE, "normalize_max_side": s.NORMALIZE_MAX_SIDE, "max_image_upload_bytes": s.MEDIA_MAX_BYTES,
            "max_video_upload_bytes": s.VIDEO_MAX_BYTES, "video_max_frames": s.VIDEO_MAX_FRAMES}
    return GateBlocked("G2", code, f"반려 — {why}", "self", 422, allowed_spec=spec, record=False)


def _encode_jpeg(img: Image.Image, s: Settings) -> bytes:
    q = s.NORMALIZE_JPEG_QUALITY
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q, optimize=True)
        if buf.tell() <= s.IMAGE_MAX_BYTES or q <= 50:
            return buf.getvalue()
        q -= 10


def _fit(img: Image.Image, fmt: str, s: Settings, steps: List[str]) -> Tuple[bytes, Image.Image]:
    w, h = img.size
    if min(w, h) < s.IMAGE_MIN_SIDE:
        raise _reject("RESOLUTION_TOO_SMALL", f"해상도 {w}×{h} — 짧은 변이 {s.IMAGE_MIN_SIDE}px 미만이다. 확대하면 검출이 부정확해져 변환하지 않는다", s)
    if max(w, h) > s.NORMALIZE_MAX_SIDE:
        r = s.NORMALIZE_MAX_SIDE / max(w, h)
        img = img.resize((max(1, round(w * r)), max(1, round(h * r))), Image.LANCZOS)
        steps.append(f"축소 {w}×{h} → {img.size[0]}×{img.size[1]}")
    if img.mode != "RGB":
        img = img.convert("RGB")
    if fmt != "JPEG":
        steps.append(f"{fmt} → JPEG")
    data = _encode_jpeg(img, s)
    return data, img


def normalize_image(data: bytes, s: Optional[Settings] = None) -> Tuple[bytes, Normalization]:
    s = s or get_settings()
    if len(data) > s.MEDIA_MAX_BYTES:
        raise _reject("UPLOAD_TOO_LARGE", f"용량 {len(data):,} B 가 업로드 한도 {s.MEDIA_MAX_BYTES:,} B 를 넘는다", s)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001
        raise _reject("FORMAT_NOT_SUPPORTED", "사진으로 읽을 수 없다 (손상 또는 지원하지 않는 형식)", s) from None
    fmt = (img.format or "UNKNOWN").upper()
    fmt = "HEIC" if fmt in ("HEIF", "HEIC") else fmt
    w, h = img.size
    source = {"format": fmt, "width": w, "height": h, "bytes": len(data)}
    steps: List[str] = []
    if _orientation(img) not in (None, 1):          # 휴대폰 세로 사진: 픽셀은 가로로 저장되고 회전은 EXIF 에만 있다
        img = ImageOps.exif_transpose(img)
        steps.append("EXIF 회전 반영")
    in_spec = (fmt in ("JPEG", "PNG") and not steps and s.IMAGE_MIN_SIDE <= min(w, h) and max(w, h) <= s.IMAGE_MAX_SIDE
               and len(data) <= s.IMAGE_MAX_BYTES)
    if in_spec:
        return data, Normalization(False, source, dict(source), [])
    out, img = _fit(img, fmt, s, steps)
    return out, Normalization(True, source, {"format": "JPEG", "width": img.size[0], "height": img.size[1], "bytes": len(out)}, steps)


def _orientation(img: Image.Image) -> Optional[int]:
    try:
        return img.getexif().get(0x0112)
    except Exception:  # noqa: BLE001
        return None


def normalize_frame(bgr: np.ndarray, s: Optional[Settings] = None) -> Tuple[bytes, Normalization]:
    """영상에서 뽑은 프레임(BGR) → 규격 JPEG."""
    s = s or get_settings()
    h, w = bgr.shape[:2]
    img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    steps: List[str] = ["영상 프레임 추출"]
    out, img = _fit(img, "JPEG", s, steps)
    return out, Normalization(True, {"format": "VIDEO_FRAME", "width": w, "height": h, "bytes": None},
                              {"format": "JPEG", "width": img.size[0], "height": img.size[1], "bytes": len(out)}, steps)


# ------------------------------------------------------------------ 영상
@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    frame_count: int
    duration_s: float
    codec: str


@contextmanager
def open_video(data: bytes, filename: str = "", s: Optional[Settings] = None) -> Iterator[Tuple[cv2.VideoCapture, VideoInfo]]:
    s = s or get_settings()
    if len(data) > s.VIDEO_MAX_BYTES:
        raise _reject("VIDEO_TOO_LARGE", f"영상 용량 {len(data):,} B 가 한도 {s.VIDEO_MAX_BYTES:,} B 를 넘는다", s)
    suffix = os.path.splitext(filename)[1][:8] or ".bin"
    fd, path = tempfile.mkstemp(prefix="cv_video_", suffix=suffix)
    cap = None
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise _reject("VIDEO_UNREADABLE", "영상으로 읽을 수 없다 (손상 또는 지원하지 않는 코덱)", s)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or n <= 0 or w <= 0:
            raise _reject("VIDEO_UNREADABLE", "영상의 길이·해상도를 읽을 수 없다", s)
        cc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((cc >> 8 * i) & 0xFF) for i in range(4)).strip("\x00 ") or "unknown"
        yield cap, VideoInfo(w, h, round(fps, 3), n, round(n / fps, 3), codec)
    finally:
        if cap is not None:
            cap.release()
        try:
            os.remove(path)          # FR-11: 원본 영상은 요청이 끝나면 남기지 않는다
        except OSError:
            pass


def sample_times(info: VideoInfo, interval_s: Optional[float], at_s: Optional[float], s: Optional[Settings] = None) -> Tuple[List[float], float]:
    """진단할 시각 목록과 실제 간격. at_s 가 있으면 그 한 장. 프레임 수 상한을 넘으면 간격을 넓힌다."""
    s = s or get_settings()
    last = max(0.0, info.duration_s - 1.0 / info.fps)
    if at_s is not None:
        if at_s < 0 or at_s > info.duration_s:
            raise _reject("TIME_OUT_OF_RANGE", f"{at_s}초 — 영상 길이({info.duration_s}초) 밖이다", s)
        return [min(at_s, last)], 0.0
    step = max(interval_s or s.VIDEO_DEFAULT_INTERVAL_S, s.VIDEO_MIN_INTERVAL_S)
    if last / step + 1 > s.VIDEO_MAX_FRAMES:
        step = last / (s.VIDEO_MAX_FRAMES - 1)
    times, t = [], 0.0
    while t <= last + 1e-6 and len(times) < s.VIDEO_MAX_FRAMES:
        times.append(round(t, 3))
        t += step
    return times, round(step, 3)


def read_frame(cap: cv2.VideoCapture, t: float) -> Optional[np.ndarray]:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, frame = cap.read()
    return frame if ok and frame is not None else None


def rolling_median(values: List[Optional[float]], window: int) -> List[Optional[float]]:
    """직전 window 개(값 있는 것만)의 중앙값 — 가림·움직임으로 튀는 값을 누른다. 실시간에도 쓸 수 있게 뒤쪽 창."""
    out: List[Optional[float]] = []
    buf: List[float] = []
    for v in values:
        if v is not None:
            buf.append(v)
            buf = buf[-window:]
        out.append(round(float(np.median(buf)), 2) if buf and v is not None else None)
    return out
