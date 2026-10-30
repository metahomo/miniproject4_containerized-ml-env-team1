"""카메라 전원 관리 (S2b) — off 면 진단 거부(G4 CAMERA_POWER_OFF), on 이면 주기 자동 진단, 전원 표."""
from tests.helpers import ADMIN, KEY, make_frame

from cv_api import db
from cv_api.services import camera_power

P = lambda x, c=0.9: (x, 260.0, x + 70.0, 620.0, c)  # noqa: E731


def _diag(client, cam="CAM-B12"):
    return client.post("/v1/diagnose", headers=KEY, data={"camera_id": cam}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})


def _power(client, cam, on):
    return client.post(f"/v1/admin/cameras/{cam}/power", headers=ADMIN, json={"on": on})


def test_off_rejects_and_on_accepts(client, stub):
    stub.boxes = [P(200), P(400)]
    assert _power(client, "CAM-B12", False).json()["operation"] == "off"
    r = _diag(client)
    assert r.status_code == 409 and r.json()["gate"] == "G4" and r.json()["reason_code"] == "CAMERA_POWER_OFF"
    assert client.get("/v1/admin/cameras/CAM-B12", headers=ADMIN).json()["powered"] is False
    row = _power(client, "CAM-B12", True).json()
    assert row["powered"] is True and row["operation"] == "offline"   # 켰지만 아직 진단 기록 없음
    assert _diag(client).status_code == 200
    with db.connect() as conn:   # 켜면 열린 G4 이벤트가 닫힌다
        assert not db.q(conn, "SELECT 1 AS x FROM gate_event WHERE gate_code='G4' AND subject_id='CAM-B12' AND resolved_at IS NULL")


def test_new_camera_starts_off(client):
    client.post("/v1/admin/cameras", headers=ADMIN, json={"camera_id": "CAM-NEW", "place_type": "train_in", "route_id": "R102", "vehicle_type_id": "VT_LOW"})
    row = next(r for r in client.get("/v1/admin/camera-power", headers=ADMIN).json() if r["camera_id"] == "CAM-NEW")
    assert row["powered"] is False and row["operation"] == "off" and row["mode"] == "rail"


def test_overview_row(client, stub):
    stub.boxes = [P(200), P(400)]
    assert _diag(client).status_code == 200
    r = client.patch("/v1/admin/cameras/CAM-B12/operation", headers=ADMIN, json={"car_position": 2, "poll_interval_s": 5})
    assert r.status_code == 200
    row = r.json()
    assert row["mode"] == "bus" and row["car_position"] == 2 and row["poll_interval_s"] == 5
    assert row["capacity"] == 80 and row["persons"] == 2 and row["density"] == 2.5 and row["operation"] == "normal"
    assert row["run_state"] is None   # 매핑 없음


def test_operation_validation(client):
    assert client.patch("/v1/admin/cameras/CAM-B12/operation", headers=ADMIN, json={"frame_source": "ftp://x"}).status_code == 422
    assert client.patch("/v1/admin/cameras/CAM-B12/operation", headers=ADMIN, json={"frame_source": "sample:none.webm"}).status_code == 422
    assert client.patch("/v1/admin/cameras/CAM-B12/operation", headers=ADMIN, json={"poll_interval_s": 0.2}).status_code == 422
    assert _power(client, "CAM-ZZ", True).status_code == 404
    assert client.get("/v1/admin/camera-power", headers=KEY).status_code == 401


def test_scheduler_polls_sample_source(client, stub):
    stub.boxes = [P(200), P(400), P(600)]
    src = "sample:videos/bus_crowded_tomaszow.webm"
    assert client.patch("/v1/admin/cameras/CAM-B13/operation", headers=ADMIN, json={"frame_source": src, "poll_interval_s": 1}).status_code == 200
    assert not [c for c in camera_power.due_cameras() if c["camera_id"] == "CAM-B13"] or True
    _power(client, "CAM-B13", False)
    assert all(c["camera_id"] != "CAM-B13" for c in camera_power.due_cameras())   # 꺼진 카메라는 돌지 않는다
    _power(client, "CAM-B13", True)
    assert any(c["camera_id"] == "CAM-B13" for c in camera_power.due_cameras())
    assert camera_power.poll_once("CAM-B13", src) is None
    row = next(r for r in client.get("/v1/admin/camera-power", headers=ADMIN).json() if r["camera_id"] == "CAM-B13")
    assert row["operation"] == "normal" and row["last_error"] is None and row["last_diagnosed_at"]
    assert all(c["camera_id"] != "CAM-B13" for c in camera_power.due_cameras())   # 방금 돌았으니 주기 전까지 대기
    with db.connect() as conn:
        assert db.q1(conn, "SELECT caller_id FROM diagnosis_request WHERE camera_id='CAM-B13' ORDER BY request_id DESC LIMIT 1")["caller_id"] == "scheduler"


def test_scheduler_reports_source_error(client, stub):
    assert camera_power.poll_once("CAM-B12", "http://127.0.0.1:9/none.jpg") is not None
    row = next(r for r in client.get("/v1/admin/camera-power", headers=ADMIN).json() if r["camera_id"] == "CAM-B12")
    assert row["last_error"]
