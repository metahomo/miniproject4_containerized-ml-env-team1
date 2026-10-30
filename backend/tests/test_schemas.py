"""T023 — 규격 반려 (FR-02, G2, SC-05): 미정의 필드·형식·해상도·용량·손상 → 422, 진단 없음."""
import io

from PIL import Image

from cv_api import db
from tests.helpers import ADMIN, KEY, make_frame


def _png(w, h):
    buf = io.BytesIO(); Image.new("RGB", (w, h), (100, 100, 100)).save(buf, "PNG"); return buf.getvalue()


def _count_assessments():
    with db.connect() as conn:
        return db.q1(conn, "SELECT COUNT(*) AS n FROM assessment")["n"]


def test_extra_field_rejected(client):
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12", "note": "x"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    assert r.status_code == 422 and r.json()["gate"] == "G2" and "note" in r.json()["reason"]
    assert _count_assessments() == 0


def test_format_rejected(client):
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.bmp", b"BM" + b"\0" * 64, "image/bmp")})
    assert r.status_code == 422 and r.json()["reason_code"] == "FORMAT_NOT_SUPPORTED"
    assert r.json()["allowed_spec"]["formats"] == ["jpeg", "png"]


def test_resolution_rejected(client):
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.png", _png(4100, 400), "image/png")})
    assert r.status_code == 422 and r.json()["reason_code"] == "RESOLUTION_OUT_OF_RANGE"
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.png", _png(200, 100), "image/png")})
    assert r.status_code == 422


def test_size_rejected(client, monkeypatch):
    from cv_api.settings import get_settings
    monkeypatch.setattr(get_settings(), "IMAGE_MAX_BYTES", 1000)
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    assert r.status_code == 422 and r.json()["reason_code"] == "SIZE_EXCEEDED"


def test_corrupt_rejected(client):
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", b"\xff\xd8\xff" + b"\0" * 300, "image/jpeg")})
    assert r.status_code == 422 and r.json()["reason_code"] == "CORRUPT"
    assert _count_assessments() == 0


def test_rejected_request_row_has_reason(client):
    client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.bmp", b"BM" + b"\0" * 64, "image/bmp")})
    with db.connect() as conn:
        row = db.q1(conn, "SELECT status, reject_reason FROM diagnosis_request ORDER BY request_id DESC LIMIT 1")
    assert row["status"] == "rejected" and row["reject_reason"]


def test_admin_json_extra_forbidden(client):
    r = client.post("/v1/admin/cameras", headers=ADMIN, json={"camera_id": "X1", "place_type": "bus_in", "bogus": 1})
    assert r.status_code == 422
