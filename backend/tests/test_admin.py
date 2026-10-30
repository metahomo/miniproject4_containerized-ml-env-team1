"""T035 — 관리 API: G1, 카메라 등록, ROI 판본·G8·roi_stale, 제원 G8, 등급 기준 G8, 유효 시간·시연 모드 G8, 매핑 G9·해제, CSV."""
from datetime import datetime, timedelta, timezone

from cv_api import db
from tests.helpers import ADMIN, KEY

FUTURE = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")


def test_admin_key_required(client):
    assert client.get("/v1/admin/cameras").status_code == 401
    assert client.get("/v1/admin/cameras", headers=KEY).status_code == 401
    assert client.get("/v1/admin/cameras", headers={"X-Admin-Key": "wrong"}).status_code == 403


def test_camera_register_and_status(client):
    r = client.post("/v1/admin/cameras", headers=ADMIN, json={"camera_id": "CAM-NEW", "place_type": "bus_in", "route_id": "R102", "vehicle_type_id": "VT_LOW"})
    assert r.status_code == 201 and r.json()["has_roi"] is False and r.json()["has_capacity"] is True
    assert client.post("/v1/admin/cameras", headers=ADMIN, json={"camera_id": "CAM-NEW", "place_type": "bus_in"}).status_code == 422
    assert client.post("/v1/admin/cameras", headers=ADMIN, json={"camera_id": "CAM-X", "place_type": "bus_in", "route_id": "R999"}).status_code == 422
    assert client.get("/v1/admin/cameras/CAM-NOPE", headers=ADMIN).status_code == 404


def test_roi_versions_and_validation(client):
    bad = client.post("/v1/admin/cameras/CAM-S03/roi", headers=ADMIN, json={"polygon": [[0, 0], [10, 10], [10, 0], [0, 10]], "effective_from": FUTURE})
    assert bad.status_code == 422 and bad.json()["gate"] == "G8"          # 자기 교차 (변 교차)
    with db.connect() as conn:
        db.update(conn, "camera", "camera_id=:c", {"roi_stale": 1}, c="CAM-B12")
    r = client.post("/v1/admin/cameras/CAM-B12/roi", headers=ADMIN, json={"polygon": [[0, 0], [100, 0], [100, 100], [0, 100]], "roi_area_m2": 5.0, "effective_from": FUTURE})
    assert r.status_code == 201 and r.json()["roi_area_m2"] == 5.0
    hist = client.get("/v1/admin/cameras/CAM-B12/roi", headers=ADMIN).json()
    assert len(hist) == 2 and sum(1 for h in hist if h["superseded_at"] is None) == 1
    assert client.get("/v1/admin/cameras/CAM-B12", headers=ADMIN).json()["roi_stale"] is False
    assert client.get("/v1/admin/cameras/CAM-B12", headers=ADMIN).json()["capacity"] == 80          # T091 현재 정원 (R22 분모)
    assert client.get("/v1/admin/cameras/CAM-S03", headers=ADMIN).json()["capacity"] is None
    dup = client.post("/v1/admin/cameras/CAM-B12/roi", headers=ADMIN, json={"polygon": [[0, 0], [100, 0], [100, 100], [0, 100]], "effective_from": FUTURE})
    assert dup.status_code == 422 and dup.json()["reason_code"] == "ROI_DUPLICATE_VERSION"


def test_spec_validation(client):
    assert client.post("/v1/admin/vehicle-types/VT_LOW/spec", headers=ADMIN, json={"capacity": 40, "seat_count": 50, "source": "x", "effective_from": FUTURE}).status_code == 422
    assert client.post("/v1/admin/vehicle-types/VT_LOW/spec", headers=ADMIN, json={"capacity": 0, "source": "x", "effective_from": FUTURE}).status_code == 422
    r = client.post("/v1/admin/vehicle-types/VT_LOW/spec", headers=ADMIN, json={"capacity": 90, "seat_count": 30, "source": "제원표 v2", "effective_from": FUTURE})
    assert r.status_code == 201 and r.json()["affected_cameras"] == 2


def test_threshold_validation(client):
    assert client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 20, "crowded_max_ratio": 50, "effective_from": FUTURE}).status_code == 422
    assert client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 120, "crowded_max_ratio": 20, "effective_from": FUTURE}).status_code == 422
    assert client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 50, "crowded_max_ratio": 20, "effective_from": "2020-01-01T00:00:00"}).status_code == 422
    r = client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 55, "crowded_max_ratio": 25, "effective_from": FUTURE})
    assert r.status_code == 201 and r.json()["is_current"] is False
    assert len(client.get("/v1/admin/policies/threshold", headers=ADMIN).json()) == 2
    # R22 인원 세기 기준: 비우면 기본 0.4 로 저장, 범위 밖은 422
    assert r.json()["count_conf_min"] == 0.4
    r2 = client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 55, "crowded_max_ratio": 25, "count_conf_min": 0.5, "effective_from": "2099-01-01T00:00:00"})
    assert r2.status_code == 201 and r2.json()["count_conf_min"] == 0.5
    assert client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 55, "crowded_max_ratio": 25, "count_conf_min": 0.99, "effective_from": "2099-02-01T00:00:00"}).status_code == 422


def test_validity_and_demo(client):
    v = client.get("/v1/admin/policies/validity", headers=ADMIN).json()
    prev = {p["route_id"]: p for p in v["preview"]}
    assert prev["R102"]["validity_minutes"] == 12 and prev["R102"]["validity_source"] == "exception"
    assert prev["R311"]["validity_minutes"] == 10 and prev["R311"]["validity_source"] == "default"
    assert prev["R102"]["route_name"] == "102번"                      # 화면이 버스 번호로 보인다 (2026-09-30)
    assert client.post("/v1/admin/policies/validity", headers=ADMIN, json={"factor": 1.0, "cap_minutes": 5, "default_minutes": 10}).status_code == 422
    assert client.post("/v1/admin/policies/validity", headers=ADMIN, json={"factor": 1.0, "cap_minutes": 30, "route_exceptions": [{"route_id": "R999", "minutes": 5}]}).status_code == 422
    r = client.post("/v1/admin/policies/validity", headers=ADMIN, json={"factor": 1.0, "cap_minutes": 30, "demo_on": True})
    assert r.status_code == 201 and r.json()["policy"]["demo_on"] is True and r.json()["policy"]["demo_end_at"]   # 기본 +2h
    with db.connect() as conn:
        assert db.q1(conn, "SELECT COUNT(*) AS n FROM validity_policy WHERE superseded_at IS NULL")["n"] == 1


def test_mapping_g9_and_release(client):
    assert client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "9999"}).status_code == 422
    r = client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "1234", "vehicle_type_id": "VT_LOW"})
    assert r.status_code == 201 and r.json()["verify_status"] == "verified"
    dup = client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "5678"})
    assert dup.status_code == 422 and dup.json()["gate"] == "G9"
    r2 = client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B13", "vehicle_id": "1234"})
    assert r2.json()["sibling_cameras"] == ["CAM-B12"]
    assert client.delete(f"/v1/admin/mappings/{r.json()['map_id']}", headers=ADMIN).status_code == 204
    assert [m["camera_id"] for m in client.get("/v1/admin/mappings", headers=ADMIN, params={"vehicle_id": "1234"}).json()] == ["CAM-B13"]


def test_csv_import(client):
    csv = "vehicle_id,camera_id,vehicle_type\n1234,CAM-B12,VT_LOW\n9999,CAM-B13,\n,CAM-S03,\n".encode("utf-8-sig")
    r = client.post("/v1/admin/mappings/csv", headers=ADMIN, files={"file": ("m.csv", csv, "text/csv")})
    j = r.json()
    assert r.status_code == 200 and j["saved"] == 1 and j["rejected"] == 2
    bad = client.post("/v1/admin/mappings/csv", headers=ADMIN, files={"file": ("m.csv", b"camera,vehicle\nA,B\n", "text/csv")})
    assert bad.status_code == 422 and "camera_id" in bad.json()["reason"]


def test_fleet_autocomplete(client):
    j = client.get("/v1/admin/fleet", headers=ADMIN, params={"route_id": "R102", "q": "12"}).json()
    assert j["source_status"] == "ok" and [v["vehicle_id"] for v in j["vehicles"]] == ["1234", "9012"]


def test_threshold_scheduled_flag_and_effective_count_conf(client):
    """2026-09-30: 예약 판본이 적용 중인 것처럼 보이던 사고 — 목록에 예약 여부, 이용자 조회에 실제 적용 중인 인원 세기 기준."""
    ref = client.get("/v1/reference/threshold", headers=KEY).json()
    assert ref["count_conf_min"] is None and ref["count_conf_min_effective"] == 0.4      # 판본 값 없음 → 설정 기본값
    client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 55, "crowded_max_ratio": 25, "count_conf_min": 0.3, "effective_from": FUTURE})
    rows = {r["policy_id"]: r for r in client.get("/v1/admin/policies/threshold", headers=ADMIN).json()}
    cur = [r for r in rows.values() if r["is_current"]]
    sched = [r for r in rows.values() if r["is_scheduled"]]
    assert len(cur) == 1 and not cur[0]["is_scheduled"]
    assert len(sched) == 1 and sched[0]["count_conf_min"] == 0.3
    assert client.get("/v1/reference/threshold", headers=KEY).json()["count_conf_min_effective"] == 0.4   # 예약은 아직 안 쓴다
