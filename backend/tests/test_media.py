"""웹 백엔드 규격 변환 — 사진 변환 규칙(축소·형식·회전, 확대 금지), 영상 프레임 추출, /v1/web/* 가 진단 API 로 넘기는 경로."""
from __future__ import annotations

import io
import os
import tempfile

import cv2
import numpy as np
import pytest
from PIL import Image

from cv_api import media
from cv_api.gates import GateBlocked
from tests.helpers import KEY, make_frame


def _img(w: int, h: int, fmt: str, exif_orientation: int | None = None) -> bytes:
    gx = np.linspace(0, 255, w, dtype="uint8")[None, :, None]          # 그라데이션 — 노이즈보다 인코딩이 빠르고 작다
    gy = np.linspace(0, 255, h, dtype="uint8")[:, None, None]
    im = Image.fromarray(np.concatenate([np.broadcast_to(gx, (h, w, 1)), np.broadcast_to(gy, (h, w, 1)), np.full((h, w, 1), 128, "uint8")], axis=2))
    buf = io.BytesIO()
    kw = {}
    if exif_orientation:
        ex = Image.Exif(); ex[0x0112] = exif_orientation; kw["exif"] = ex.tobytes()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def _video(seconds: int = 6, fps: int = 5, size=(1280, 720)) -> bytes:
    fd, p = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
    frame = cv2.imdecode(np.frombuffer(make_frame(*size), np.uint8), cv2.IMREAD_COLOR)
    w = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for _ in range(seconds * fps):
        w.write(frame)
    w.release()
    data = open(p, "rb").read(); os.remove(p)
    return data


# ---------------------------------------------------------------- 사진 규칙
def test_in_spec_jpeg_passes_through_unchanged():
    data = make_frame(1280, 720)
    out, n = media.normalize_image(data)
    assert out == data and n.applied is False


def test_large_png_is_downscaled_to_jpeg():
    out, n = media.normalize_image(_img(5000, 3000, "PNG"))
    assert n.applied and n.as_dict()["to"] == {"format": "JPEG", "width": 1920, "height": 1152, "bytes": len(out)}
    assert Image.open(io.BytesIO(out)).format == "JPEG"


def test_webp_is_converted():
    out, n = media.normalize_image(_img(800, 600, "WEBP"))
    assert n.applied and "WEBP → JPEG" in n.steps and Image.open(io.BytesIO(out)).size == (800, 600)


def test_exif_rotation_is_applied():
    out, n = media.normalize_image(_img(800, 600, "JPEG", exif_orientation=6))
    assert "EXIF 회전 반영" in n.steps and Image.open(io.BytesIO(out)).size == (600, 800)


def test_heic_is_converted():
    import pillow_heif
    buf = io.BytesIO()
    try:
        pillow_heif.from_pillow(Image.fromarray(np.zeros((600, 800, 3), np.uint8))).save(buf, quality=80)
    except Exception:  # noqa: BLE001
        pytest.skip("HEIF 인코더 없음")
    out, n = media.normalize_image(buf.getvalue())
    assert n.source["format"] == "HEIC" and Image.open(io.BytesIO(out)).format == "JPEG"


def test_too_small_is_rejected_not_upscaled():
    with pytest.raises(GateBlocked) as e:
        media.normalize_image(_img(320, 200, "PNG"))
    assert e.value.gate == "G2" and e.value.reason_code == "RESOLUTION_TOO_SMALL" and e.value.http_status == 422


def test_garbage_is_rejected():
    with pytest.raises(GateBlocked) as e:
        media.normalize_image(b"not an image" * 10)
    assert e.value.reason_code == "FORMAT_NOT_SUPPORTED"


# ---------------------------------------------------------------- 영상 규칙
def test_sample_times_caps_frame_count():
    info = media.VideoInfo(640, 480, 30.0, 30 * 600, 600.0, "avc1")    # 10분
    times, step = media.sample_times(info, 2.0, None)
    assert len(times) == 60 and step > 2.0 and times[0] == 0.0


def test_sample_times_single_and_out_of_range():
    info = media.VideoInfo(640, 480, 5.0, 30, 6.0, "mp4v")
    assert media.sample_times(info, None, 3.0) == ([3.0], 0.0)
    with pytest.raises(GateBlocked):
        media.sample_times(info, None, 9.0)


def test_rolling_median_skips_gaps():
    assert media.rolling_median([10, None, 50, 12, 11], 3) == [10, None, 30, 12, 12]


def test_video_temp_file_is_removed():
    before = set(os.listdir(tempfile.gettempdir()))
    with media.open_video(_video(2), "a.mp4") as (_cap, info):
        assert info.duration_s == pytest.approx(2.0, abs=0.3)
    leaked = [f for f in set(os.listdir(tempfile.gettempdir())) - before if f.startswith("cv_video_")]
    assert leaked == []


# ---------------------------------------------------------------- /v1/web/* → 진단 API
@pytest.fixture()
def web(stub, monkeypatch):
    from fastapi.testclient import TestClient
    from cv_api.app import create_app
    from cv_api.routers import web_media

    from tests.conftest import _noop_lifespan

    # 전체 앱 하나(R21-D1)가 /v1/web/* 를 자기 진단 경로로 중계한다. lifespan 은 끈다 — stub 픽스처가 이미 ready 로 만들었고,
    # 켜 두면 백그라운드 적재가 끝나기 전에 첫 요청이 G0(503)을 받는 경쟁이 부하 높은 공유 서버에서 난다
    app = create_app("all")
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        monkeypatch.setattr(web_media, "_api_client", lambda s: _NoClose(c))
        yield c


class _NoClose:
    """_relay 의 `with` 가 공유 TestClient 를 닫지 않게 감싼다."""

    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self.c

    def __exit__(self, *a):
        return False


def test_web_diagnose_converts_then_diagnoses(web, stub):
    stub.boxes = [(400, 200, 500, 600, 0.9)]
    r = web.post("/v1/web/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"file": ("big.png", _img(5000, 3000, "PNG"), "image/png")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["normalization"]["applied"] and j["normalization"]["from"]["format"] == "PNG"
    assert "vacant_capacity_ratio" in j and j["camera_id"] == "CAM-B12"


def test_web_diagnose_small_rejected_before_api(web):
    r = web.post("/v1/web/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"file": ("s.png", _img(300, 200, "PNG"), "image/png")})
    assert r.status_code == 422 and r.json()["reason_code"] == "RESOLUTION_TOO_SMALL"


def test_web_diagnose_passes_api_rejection_through(web):
    r = web.post("/v1/web/diagnose", headers=KEY, data={"camera_id": "CAM-XX"}, files={"file": ("f.jpg", make_frame(), "image/jpeg")})
    assert r.status_code == 404 and r.json()["gate"] == "G3" and r.json()["normalization"]["applied"] is False


def test_web_requires_key(web):
    r = web.post("/v1/web/diagnose", data={"camera_id": "CAM-B12"}, files={"file": ("f.jpg", make_frame(), "image/jpeg")})
    assert r.status_code == 401


def test_web_video_interval(web, stub):
    stub.boxes = [(400, 200, 500, 600, 0.9)]
    r = web.post("/v1/web/diagnose-video", headers=KEY, data={"camera_id": "CAM-B12", "interval_s": "2", "started_at": "2026-09-29T08:30:00"},
                 files={"file": ("v.mp4", _video(6), "video/mp4")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "interval" and [it["t"] for it in j["items"]] == [0.0, 2.0, 4.0]
    assert all(it["status"] == "accepted" for it in j["items"]) and j["summary"]["accepted"] == 3
    assert j["items"][1]["assessment"]["captured_at"].startswith("2026-09-29T08:30:02")
    assert j["items"][0]["smoothed_vacant_ratio"] == j["items"][0]["assessment"]["vacant_capacity_ratio"]


def test_web_video_single_frame(web):
    r = web.post("/v1/web/diagnose-video", headers=KEY, data={"camera_id": "CAM-B12", "at_s": "3.5"}, files={"file": ("v.mp4", _video(6), "video/mp4")})
    assert r.status_code == 200 and r.json()["mode"] == "single" and len(r.json()["items"]) == 1


def test_web_video_stops_on_camera_gate(web):
    r = web.post("/v1/web/diagnose-video", headers=KEY, data={"camera_id": "CAM-XX"}, files={"file": ("v.mp4", _video(6), "video/mp4")})
    assert r.status_code == 404 and r.json()["gate"] == "G3" and r.json()["stopped_at_s"] == 0.0


def test_web_video_unreadable(web):
    r = web.post("/v1/web/diagnose-video", headers=KEY, data={"camera_id": "CAM-B12"}, files={"file": ("v.mp4", b"\x00" * 5000, "video/mp4")})
    assert r.status_code == 422 and r.json()["reason_code"] == "VIDEO_UNREADABLE"


# ---------------------------------------------------------------- /v1/web/samples (S5 샘플 선택)
def test_web_samples_listed_and_served(web):
    r = web.get("/v1/web/samples", headers=KEY)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items and all(it["kind"] in ("video", "image") and it["license"] and it["source_url"] for it in items)
    assert {it["kind"] for it in items} == {"video", "image"}
    first = items[0]
    f = web.get(f"/v1/web/samples/{first['file']}", headers=KEY)
    assert f.status_code == 200 and f.headers["content-type"] == first["content_type"] and len(f.content) == first["bytes"]


def test_web_samples_only_catalog_files(web):
    assert web.get("/v1/web/samples/catalog.json", headers=KEY).status_code == 404
    assert web.get("/v1/web/samples/..%2Fcv_api%2Fsettings.py", headers=KEY).status_code == 404
    assert web.get("/v1/web/samples").status_code == 401


def test_web_sample_video_diagnoses(web, stub):
    """샘플 영상(webm/VP9)을 받아 그대로 영상 진단에 넣으면 서버가 읽는다."""
    stub.boxes = [(400, 200, 500, 600, 0.9)]
    first = next(it for it in web.get("/v1/web/samples", headers=KEY).json() if it["kind"] == "video")
    data = web.get(f"/v1/web/samples/{first['file']}", headers=KEY).content
    r = web.post("/v1/web/diagnose-video", headers=KEY, data={"camera_id": "CAM-B12", "at_s": "1"},
                 files={"file": (first["file"].rsplit("/", 1)[-1], data, first["content_type"])})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["status"] == "accepted"
