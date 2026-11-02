"""T099 — 이용자는 카메라 번호·내부 코드 없이 버스 상태를 본다: 노선·정류장 이름 검색, 버스 번호로 상태, 후속 차량의 인원/정원."""
from tests.helpers import ADMIN, KEY, make_frame

P = lambda x: (x, 260.0, x + 70.0, 620.0, 0.9)  # noqa: E731


def test_routes_and_stops_by_name(client):
    r = client.get("/v1/reference/routes", headers=KEY, params={"q": "102"}).json()
    assert [x["route_id"] for x in r] == ["R102"] and r[0]["route_no"] == "102번"
    all_routes = client.get("/v1/reference/routes", headers=KEY).json()
    assert {x["route_id"] for x in all_routes} >= {"R102", "R311"}
    stops = client.get("/v1/reference/stops", headers=KEY, params={"route_id": "R102"}).json()
    assert "3001" in {s["stop_id"] for s in stops}
    found = client.get("/v1/reference/stops", headers=KEY, params={"q": "충남대"}).json()
    assert found and all("충남대" in s["stop_name"] for s in found) and found[0]["route_no"]
    assert client.get("/v1/reference/stops", headers=KEY).status_code == 422          # route_id 나 q 중 하나는 필요
    assert client.get("/v1/reference/routes").status_code == 401                     # 호출 키 필요


def test_routes_at_stop(client):
    """T109 — 정류장을 누르면 그 정류장에 서는 버스 번호만. BIS 형식(노선ID:정류소ID)은 정류소 ID 로, 고정 자료는 이름으로 묶는다."""
    from cv_api import db
    with db.connect() as conn:
        for rid, no in (("99001", "901번"), ("99002", "15번"), ("99003", "7번")):
            db.insert(conn, "route", {"route_id": rid, "mode": "bus", "route_name": f"{no} ({rid})", "source": "test"})
        for sid, rid, name in (("99001:900", "99001", "시청 (A 방면)"), ("99002:900", "99002", "시청 (A 방면)"),
                               ("99003:901", "99003", "시청 (B 방면)"), ("99003:1900", "99003", "다른곳")):
            db.insert(conn, "stop", {"stop_id": sid, "route_id": rid, "stop_name": name, "place_kind": "bus_stop"})
    r = client.get("/v1/reference/stops/99001:900/routes", headers=KEY).json()
    assert [(x["route_no"], x["stop_id"]) for x in r] == [("15번", "99002:900"), ("901번", "99001:900")]   # 반대 방향(901)·끝자리만 같은 1900 은 빠진다
    r = client.get("/v1/reference/stops/3001/routes", headers=KEY).json()                              # 고정 자료: 이름 '충남대'
    assert [x["route_id"] for x in r] == ["R102"]
    assert client.get("/v1/reference/stops/NOPE/routes", headers=KEY).status_code == 404


def test_vehicle_status_by_number_and_next_vehicle_headcount(client, stub):
    assert client.get("/v1/vehicles/1234", headers=KEY).json()["basis_type"] == "no_measurement"   # 실측 없으면 추정하지 않는다
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "1234"})
    stub.boxes = [P(100 + i * 60) for i in range(18)]
    assert client.post("/v1/measurements", headers=KEY, data={"vehicle_id": "1234", "camera_id": "CAM-B12"},
                       files={"frame": ("f.jpg", make_frame(), "image/jpeg")}).status_code == 200
    v = client.get("/v1/vehicles/1234", headers=KEY).json()
    assert v["basis_type"] == "measured" and (v["persons_sum"], v["capacity"]) == (18, 80) and v["vacant_ratio"] == 77.5
    assert v["crowding_level"] == "free" and v["measured_at"] and v["expires_at"] and v["notice"]
    nv = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001"}).json()
    it = next(x for x in nv["vehicles"] if x["vehicle_id"] == "1234")
    assert (it["persons_sum"], it["capacity"]) == (18, 80)                              # S7 "18 / 80명"
