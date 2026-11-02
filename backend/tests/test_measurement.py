"""T042 — 실측 등록 (UC10, P6): G10, 판독 불확실 실측 인정, 대체, 합산·커버리지, 만료 시각, 시연 모드."""
from cv_api import db
from tests.helpers import ADMIN, KEY, make_frame

P = lambda x, c=0.9: (x, 260.0, x + 70.0, 620.0, c)  # noqa: E731


def _map(client, cam, veh):
    return client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": cam, "vehicle_id": veh, "vehicle_type_id": "VT_LOW"})


def _meas(client, veh, cam, **kw):
    return client.post("/v1/measurements", headers=KEY, data={"vehicle_id": veh, "camera_id": cam, **kw}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})


def test_g10_mapping_missing_and_platform(client):
    r = _meas(client, "1234", "CAM-B12")
    assert r.status_code == 409 and r.json()["gate"] == "G10" and r.json()["gate_event_id"]
    r = _meas(client, "1234", "CAM-S03")                     # UC10 A3: 승강장 카메라는 실측 불가 (R21-D8 정정)
    assert r.status_code == 409 and r.json()["reason_code"] == "NOT_IN_VEHICLE_CAMERA"


def test_train_in_vehicle_camera_measurement(client, stub):
    """R21-D8 정정: 열차 차내 카메라(train_in)도 버스 차내와 같이 실측으로 저장."""
    assert client.post("/v1/admin/cameras", headers=ADMIN, json={"camera_id": "CAM-T01", "place_type": "train_in", "route_id": "R102", "vehicle_type_id": "VT_LOW"}).status_code in (200, 201)
    roi = {"polygon": [[100, 300], [1180, 300], [1180, 700], [100, 700]], "roi_area_m2": 6.5, "effective_from": "2026-01-01T00:00:00Z"}
    assert client.post("/v1/admin/cameras/CAM-T01/roi", headers=ADMIN, json=roi).status_code in (200, 201)
    assert _map(client, "CAM-T01", "5678").status_code in (200, 201)
    stub.boxes = [P(200), P(400)]
    r = _meas(client, "5678", "CAM-T01")
    assert r.status_code == 409 and r.json()["reason_code"] == "CAMERA_POWER_OFF"   # 새 카메라는 꺼진 채 등록된다 (S2b)
    assert client.post("/v1/admin/cameras/CAM-T01/power", headers=ADMIN, json={"on": True}).status_code == 200
    r = _meas(client, "5678", "CAM-T01")
    assert r.status_code == 200, r.json()
    m = r.json()["measurement"]
    assert m["vehicle_id"] == "5678" and m["coverage_num"] == 1 and m["vacant_ratio_agg"] is not None


def test_measurement_and_aggregate(client, stub):
    _map(client, "CAM-B12", "1234"); _map(client, "CAM-B13", "1234")
    stub.boxes = [P(100 + i * 60) for i in range(18)]       # 18명
    r = _meas(client, "1234", "CAM-B12")
    m = r.json()["measurement"]
    assert r.status_code == 200 and m["coverage_num"] == 1 and m["coverage_den"] == 2 and m["partial_coverage"] is True
    assert m["persons_sum"] == 18 and m["capacity"] == 80 and m["vacant_ratio_agg"] == 77.5
    assert m["applied_validity_minutes"] == 12 and m["demo_mode"] is False
    stub.boxes = [P(200), P(400)]                             # 2명
    m2 = _meas(client, "1234", "CAM-B13").json()["measurement"]
    assert m2["coverage_num"] == 2 and m2["coverage_den"] == 2 and m2["partial_coverage"] is False
    # R22 카메라 합산: (18 + 2) ÷ 차량 정원 80 = 25% 점유 → 잔여 75% → free
    assert m2["persons_sum"] == 20 and m2["vacant_ratio_agg"] == 75.0 and m2["crowding_level_agg"] == "free"
    with db.connect() as conn:
        assert db.q1(conn, "SELECT COUNT(*) AS n FROM camera_measurement WHERE superseded_at IS NULL")["n"] == 2
        assert db.q1(conn, "SELECT COUNT(*) AS n FROM vehicle_measurement WHERE superseded_at IS NULL")["n"] == 1


def test_uncertain_kept_as_measurement(client, stub):
    _map(client, "CAM-B12", "1234")
    stub.boxes = [P(200, 0.4)]
    r = _meas(client, "1234", "CAM-B12")
    assert r.status_code == 200 and r.json()["assessment"]["crowding_level"] == "uncertain"
    assert r.json()["measurement"]["crowding_level_agg"] == "uncertain"


def test_supersede_previous(client, stub):
    _map(client, "CAM-B12", "1234")
    stub.boxes = [P(200)]
    _meas(client, "1234", "CAM-B12"); _meas(client, "1234", "CAM-B12")
    with db.connect() as conn:
        rows = db.q(conn, "SELECT superseded_at FROM camera_measurement ORDER BY cm_id")
    assert rows[0]["superseded_at"] is not None and rows[1]["superseded_at"] is None


def test_already_expired_captured_at(client, stub):
    _map(client, "CAM-B12", "1234")
    stub.boxes = [P(200)]
    m = _meas(client, "1234", "CAM-B12", captured_at="2026-01-01T00:00:00").json()["measurement"]
    assert m["already_expired"] is True


def test_demo_mode_uses_registered_at(client, stub):
    _map(client, "CAM-B12", "1234")
    client.post("/v1/admin/policies/validity", headers=ADMIN, json={"factor": 1.0, "cap_minutes": 30, "demo_on": True})
    stub.boxes = [P(200)]
    m = _meas(client, "1234", "CAM-B12", captured_at="2026-01-01T00:00:00").json()["measurement"]
    assert m["demo_mode"] is True and m["already_expired"] is False


def test_release_mapping_invalidates(client, stub):
    r = _map(client, "CAM-B12", "1234")
    stub.boxes = [P(200)]
    _meas(client, "1234", "CAM-B12")
    client.delete(f"/v1/admin/mappings/{r.json()['map_id']}", headers=ADMIN)
    with db.connect() as conn:
        assert db.q1(conn, "SELECT COUNT(*) AS n FROM v_vehicle_measurement_status WHERE vehicle_id='1234'")["n"] == 0


def test_requested_gate_events_listed_for_s1(client):
    """결정 D10: C7 «요청 보내기»를 한 미해제 게이트만 S1 '받은 요청'으로 나온다."""
    ev = _meas(client, "1234", "CAM-B12").json()["gate_event_id"]          # G10 매핑 없음 — 해제 주체 운영 관리자
    assert client.get("/v1/admin/gate-events", headers=ADMIN, params={"requested_only": True}).json() == []
    assert client.post(f"/v1/gate-events/{ev}/request", headers=KEY).status_code == 200
    got = client.get("/v1/admin/gate-events", headers=ADMIN, params={"requested_only": True}).json()
    assert [g["event_id"] for g in got] == [ev] and got[0]["request_sent_by"] and got[0]["request_sent_at"]
