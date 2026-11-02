"""시연 예비 절차 (2026-09-29 사용자 결정 ③) — 실제 BIS(102번 30300037·충남대학교) 장애 시 EXTERNAL_PROVIDER=fixture 로 되돌려도
시연 화면의 노선·정류장이 그대로 동작해야 한다. fixture 에 30300037 복제본이 있다(data/fixtures/transit.json)."""
from cv_api import db
from tests.helpers import ADMIN, KEY

ROUTE, STOP = "30300037", "30300037:42620"


def _seed_bis_camera():
    now = db.now_iso()
    with db.connect() as conn:
        db.insert(conn, "route", {"route_id": ROUTE, "mode": "bus", "route_name": "102번 (30300037)", "source": "BIS"})
        db.insert(conn, "stop", {"stop_id": STOP, "route_id": ROUTE, "stop_name": "충남대학교", "place_kind": "bus_stop"})
        db.insert(conn, "camera", {"camera_id": "CAM-DEMO-01", "place_type": "bus_in", "route_id": ROUTE, "stop_id": None,
                                   "vehicle_type_id": "VT_LOW", "roi_stale": 0, "registered_at": now, "registered_by": "t"})
        # 실제 BIS 때 연결돼 있던 차량(오늘 운행) — fixture 에도 있는 번호
        db.insert(conn, "camera_vehicle_map", {"camera_id": "CAM-DEMO-01", "vehicle_id": "대전75자9016", "vehicle_type_id": "VT_LOW",
                                               "verify_status": "verified", "verified_at": now, "effective_from": now, "released_at": None,
                                               "created_at": now, "created_by": "t", "input_method": "select"})


def test_fixture_fallback_keeps_demo_route_working(client):
    _seed_bis_camera()
    j = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": ROUTE, "stop_id": STOP, "limit": 3}).json()
    assert j["source_status"] == "ok" and [v["vehicle_id"] for v in j["vehicles"]] == ["대전75자9015", "대전75자9017", "대전75자2014"]
    r = client.post("/v1/admin/demo/bis-remap", headers=ADMIN, json={"route_id": ROUTE, "stop_id": STOP, "camera_ids": ["CAM-DEMO-01"]})
    assert r.status_code == 200 and r.json()["changed"] == 1                    # 도착 1순위 차량으로 다시 연결 (G9 는 fixture 차량 목록으로 통과)
    maps = {m["camera_id"]: m["vehicle_id"] for m in client.get("/v1/admin/mappings", headers=ADMIN).json()}
    assert maps["CAM-DEMO-01"] == "대전75자9015"
