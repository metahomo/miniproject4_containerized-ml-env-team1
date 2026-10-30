"""T043 — 후속 차량 여유도 (UC2, P7): G11, measured / no_measurement / unavailable, 장애 격리(NFR-08), 무차등(FR-16)."""
from cv_api import external
from tests.helpers import ADMIN, KEY, make_frame

P = lambda x: (x, 260.0, x + 70.0, 620.0, 0.9)  # noqa: E731


def test_g11(client):
    r = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "9999"})
    assert r.status_code == 404 and r.json()["gate"] == "G11"
    assert client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R999", "stop_id": "3001"}).status_code == 404


def test_no_measurement_no_estimate(client):
    j = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001", "limit": 4}).json()
    assert j["source_status"] == "ok" and len(j["vehicles"]) == 4
    for v in j["vehicles"]:
        assert v["basis_type"] == "no_measurement" and v["vacant_ratio"] is None and v["crowding_level"] is None
    assert j["applied_validity_minutes"] == 12 and j["notice"]


def test_measured_and_uncertain_passthrough(client, stub):
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "1234"})
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B13", "vehicle_id": "5678"})
    stub.boxes = [P(90 + i * 15) for i in range(66)]          # 66 ÷ 80 → 잔여 17.5% crowded
    client.post("/v1/measurements", headers=KEY, data={"vehicle_id": "1234", "camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    stub.boxes = [(200, 260, 270, 620, 0.4)]
    client.post("/v1/measurements", headers=KEY, data={"vehicle_id": "5678", "camera_id": "CAM-B13"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    j = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001", "limit": 4}).json()
    by = {v["vehicle_id"]: v for v in j["vehicles"]}
    assert by["1234"]["basis_type"] == "measured" and by["1234"]["crowding_level"] == "crowded" and by["1234"]["measured_at"]
    assert by["5678"]["basis_type"] == "measured" and by["5678"]["crowding_level"] == "uncertain"
    assert "low_confidence" in [w["code"] for w in by["5678"]["warnings"]]
    assert by["9012"]["basis_type"] == "no_measurement"


def test_unavailable_isolated_from_diagnosis(client, stub):
    prov = external.get_providers()
    prov.arrival.fail_arrivals = True
    try:
        j = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001"}).json()
        assert j["source_status"] == "unavailable" and j["vehicles"][0]["basis_type"] == "unavailable"
        r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
        assert r.status_code == 200
    finally:
        prov.arrival.fail_arrivals = False


def test_same_values_for_any_caller(client):
    a = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001"}).json()
    b = client.get("/v1/next-vehicle", headers=ADMIN, params={"route_id": "R102", "stop_id": "3001"}).json()
    assert [(v["vehicle_id"], v["basis_type"]) for v in a["vehicles"]] == [(v["vehicle_id"], v["basis_type"]) for v in b["vehicles"]]


def test_rate_limited_reported_and_recorded_as_unavailable(client, monkeypatch):
    """BIS 한도 초과(429): 응답 source_status=rate_limited(화면 안내용), DB 에는 CHECK 허용값 unavailable 로 — 500 이 나면 안 된다."""
    from cv_api import db
    from cv_api.external.base import ArrivalResult
    prov = external.get_providers()
    monkeypatch.setattr(prov.arrival, "next_arrivals", lambda *a, **k: ArrivalResult(source_status="rate_limited"))
    r = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001"})
    assert r.status_code == 200 and r.json()["source_status"] == "rate_limited" and r.json()["vehicles"][0]["basis_type"] == "unavailable"
    with db.connect() as conn:
        assert db.q1(conn, "SELECT source_status FROM arrival_snapshot ORDER BY fetched_at DESC LIMIT 1")["source_status"] == "unavailable"
