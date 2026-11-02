"""T097 — 시연 카메라를 도착 예정 차량으로 다시 연결 (S8). fixture 도착 순서: 3001 정류장 1234 → 5678 → 9012 → 3456."""
from cv_api import external
from tests.helpers import ADMIN, KEY

BODY = {"route_id": "R102", "stop_id": "3001", "camera_ids": ["CAM-B12", "CAM-B13"]}


def _active(client):
    return {m["camera_id"]: m["vehicle_id"] for m in client.get("/v1/admin/mappings", headers=ADMIN).json()}


def test_remap_keeps_arriving_and_replaces_others(client):
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "5678"})   # 목표(앞 2대) 안 → 그대로
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B13", "vehicle_id": "3456"})   # 목표 밖 → 교체
    r = client.post("/v1/admin/demo/bis-remap", headers=ADMIN, json=BODY)
    j = r.json()
    assert r.status_code == 200 and j["source_status"] == "ok" and j["changed"] == 1
    assert [(x["camera_id"], x["before"], x["after"], x["action"]) for x in j["rows"]] == [
        ("CAM-B12", "5678", "5678", "kept"), ("CAM-B13", "3456", "1234", "changed")]
    assert j["rows"][1]["expected_arrival_at"]
    assert _active(client) == {"CAM-B12": "5678", "CAM-B13": "1234"}
    # 다시 눌러도 바뀌지 않는다 (멱등)
    assert client.post("/v1/admin/demo/bis-remap", headers=ADMIN, json=BODY).json()["changed"] == 0


def test_remap_unmapped_cameras_get_arrival_order(client):
    j = client.post("/v1/admin/demo/bis-remap", headers=ADMIN, json=BODY).json()
    assert [(x["before"], x["after"]) for x in j["rows"]] == [(None, "1234"), (None, "5678")]
    assert _active(client) == {"CAM-B12": "1234", "CAM-B13": "5678"}


def test_remap_does_nothing_when_feed_down(client):
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "3456"})
    prov = external.get_providers()
    prov.arrival.fail_arrivals = True
    try:
        j = client.post("/v1/admin/demo/bis-remap", headers=ADMIN, json=BODY).json()
    finally:
        prov.arrival.fail_arrivals = False
    assert j["changed"] == 0 and j["source_status"] == "unavailable" and "바꾸지 않았다" in j["message"]
    assert _active(client) == {"CAM-B12": "3456"}


def test_remap_admin_only_and_unknown_camera(client):
    assert client.post("/v1/admin/demo/bis-remap", headers=KEY, json=BODY).status_code in (401, 403)
    r = client.post("/v1/admin/demo/bis-remap", headers=ADMIN, json={**BODY, "camera_ids": ["CAM-XX"]})
    assert r.status_code == 404 and r.json()["gate"] == "G3"
