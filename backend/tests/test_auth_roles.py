"""T095 — 이용자/관리자 인증 (UC_00 §4 액터, G1). 이용자(호출 키)는 조회 경로로 S0·S5·S6·S7 표시 정보를 읽고, 변경은 관리자 키만."""
from tests.helpers import ADMIN, KEY


def test_whoami_roles(client):
    w = lambda h: {k: v for k, v in client.get("/v1/auth/whoami", headers=h).json().items() if k in ("caller_id", "role")}  # noqa: E731
    assert w(KEY) == {"caller_id": "web", "role": "webservice"}              # 본 웹서비스 (서버 설정 호출 키)
    assert w(ADMIN) == {"caller_id": "op1", "role": "admin"}                  # 최초 운영 관리자 (관리자 키)
    # 웹 화면은 호출 키를 늘 보내고 로그인 때 관리자 키를 더한다 — 틀린 관리자 키면 본 웹서비스로
    assert w({**KEY, "X-Admin-Key": "wrong"})["role"] == "webservice"
    assert w({**KEY, **ADMIN})["role"] == "admin"
    assert client.get("/v1/auth/whoami").status_code == 401


def test_user_reads_reference_without_admin(client):
    cams = client.get("/v1/reference/cameras", headers=KEY).json()
    b12 = next(c for c in cams if c["camera_id"] == "CAM-B12")
    assert b12["capacity"] == 80 and b12["has_roi"] is True
    assert client.get("/v1/reference/cameras/CAM-B12", headers=KEY).json()["capacity"] == 80
    roi = client.get("/v1/reference/cameras/CAM-B12/roi", headers=KEY).json()
    assert len(roi["polygon"]) == 4
    assert client.get("/v1/reference/cameras/CAM-S03/roi", headers=KEY).status_code == 404
    t = client.get("/v1/reference/threshold", headers=KEY).json()
    assert (t["free_min_ratio"], t["crowded_max_ratio"]) == (50, 20)
    assert "demo_on" in client.get("/v1/reference/ops-status", headers=KEY).json()
    assert client.get("/v1/reference/cameras").status_code == 401            # 호출 키는 필요


def test_user_cannot_change_anything(client):
    """UC6 E3·UC7 E2·UC8 E2·UC12 E4 — 운영 관리자가 아닌 주체의 변경 시도는 거부 (G1)."""
    attempts = [
        ("post", "/v1/admin/cameras/CAM-B12/roi", {"polygon": [[0, 0], [9, 0], [9, 9]], "effective_from": "2099-01-01T00:00:00"}),
        ("post", "/v1/admin/vehicle-types/VT_LOW/spec", {"capacity": 5, "source": "x", "effective_from": "2099-01-01T00:00:00"}),
        ("post", "/v1/admin/policies/threshold", {"free_min_ratio": 60, "crowded_max_ratio": 10, "effective_from": "2099-01-01T00:00:00"}),
        ("post", "/v1/admin/mappings", {"camera_id": "CAM-B12", "vehicle_id": "1234"}),
        ("get", "/v1/admin/cameras", None),
    ]
    for method, path, body in attempts:
        r = getattr(client, method)(path, headers=KEY, **({"json": body} if body else {}))
        assert r.status_code == 401 and r.json()["gate"] == "G1", path
    r = client.post("/v1/admin/policies/threshold", headers={**KEY, "X-Admin-Key": "wrong"}, json=attempts[2][2])
    assert r.status_code == 403 and r.json()["reason_code"] == "ADMIN_INVALID"
