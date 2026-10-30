"""S10 권한 매트릭스 — 운영 관리자가 역할×기능 칸을 켜고 끄면 실제 호출이 그대로 따른다. 잠긴 칸은 못 바꾼다."""
from tests.helpers import ADMIN, KEY, make_frame

USER = {"login_id": "dev.kim", "name": "김개발", "password": "pw-12345678"}


def _user(client):
    client.post("/v1/auth/signup", json=USER)
    r = client.post("/v1/auth/login", json={"login_id": USER["login_id"], "password": USER["password"]})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _row(view, perm):
    return next(p for p in view["permissions"] if p["permission"] == perm)


def _put(client, headers, **perms):
    return client.put("/v1/admin/rbac", headers=headers, json={"permissions": perms})


def test_view_shape_and_defaults(client):
    v = client.get("/v1/admin/rbac", headers=ADMIN).json()
    assert [r["role"] for r in v["roles"]] == ["user", "integration", "webservice", "controller", "admin"]
    assert v["changed_cells"] == 0 and v["updated_at"] is None
    m = _row(v, "measure")
    assert m["roles"] == m["default_roles"] and "user" not in m["roles"] and m["locked_roles"] == ["admin"]
    assert _row(v, "accounts")["locked_roles"] == ["user", "integration", "webservice", "controller", "admin"]


def test_toggle_cells_changes_access(client):
    U = _user(client)
    assert client.get("/v1/reference/cameras", headers=U).status_code == 200
    # 일반 사용자의 «기준 정보 보기» 끄기 → 403, 다른 역할(서버 호출 키)은 그대로
    roles = [r for r in _row(client.get("/v1/admin/rbac", headers=ADMIN).json(), "reference_read")["roles"] if r != "user"]
    v = _put(client, ADMIN, reference_read=roles).json()
    assert v["changed_cells"] == 1 and v["updated_by"] == "op1" and "user" not in _row(v, "reference_read")["roles"]
    r = client.get("/v1/reference/cameras", headers=U)
    assert r.status_code == 403 and r.json()["reason_code"] == "ROLE_FORBIDDEN"
    assert client.get("/v1/reference/cameras", headers=KEY).status_code == 200
    assert "reference_read" not in client.get("/v1/auth/me", headers=U).json()["permissions"]
    w = client.get("/v1/auth/whoami", headers=U)
    assert w.status_code == 200                                                   # 로그인 확인은 막지 않는다
    assert "reference_read" not in w.json()["permissions"] and "diagnose" in w.json()["permissions"]   # 웹 메뉴·게이트가 따르는 유효 권한
    # 기본값으로 되돌리면 저장된 칸이 없어진다
    assert _put(client, ADMIN, reference_read=roles + ["user"]).json()["changed_cells"] == 0
    assert client.get("/v1/reference/cameras", headers=U).status_code == 200


def test_measure_default_denied_and_grant(client, stub):
    U = _user(client)
    files = {"frame": ("f.jpg", make_frame(), "image/jpeg")}
    r = client.post("/v1/measurements", headers=U, data={"vehicle_id": "V1", "camera_id": "CAM-B12"}, files=files)
    assert r.status_code == 403 and r.json()["reason_code"] == "ROLE_FORBIDDEN"    # 표대로: 일반 사용자는 실측 등록 불가
    cur = _row(client.get("/v1/admin/rbac", headers=ADMIN).json(), "measure")["roles"]
    _put(client, ADMIN, measure=cur + ["user"])
    r = client.post("/v1/measurements", headers=U, data={"vehicle_id": "V1", "camera_id": "CAM-B12"}, files=files)
    assert r.status_code != 403


def test_control_view_grant_opens_read_paths_only(client):
    U = _user(client)
    assert client.get("/v1/admin/gate-events", headers=U).status_code == 403
    cur = _row(client.get("/v1/admin/rbac", headers=ADMIN).json(), "control_view")["roles"]
    _put(client, ADMIN, control_view=cur + ["user"])
    assert client.get("/v1/admin/gate-events", headers=U).status_code == 200
    assert client.get("/v1/admin/policies/threshold", headers=U).status_code == 403  # 관리 경로는 여전히 운영 관리자만


def test_locked_unknown_and_non_admin(client):
    r = _put(client, ADMIN, accounts=["admin", "controller"])
    assert r.status_code == 422 and r.json()["reason_code"] == "RBAC_LOCKED"
    r = _put(client, ADMIN, diagnose=["user"])                                      # 운영 관리자 열을 끄려 함
    assert r.status_code == 422 and r.json()["reason_code"] == "RBAC_LOCKED"
    r = _put(client, ADMIN, diagnose=["admin", "guest"])
    assert r.status_code == 422 and r.json()["reason_code"] == "RBAC_UNKNOWN"
    assert client.get("/v1/admin/rbac", headers=ADMIN).json()["changed_cells"] == 0
    client.post("/v1/admin/accounts", headers=ADMIN, json={"login_id": "ctl.lee", "name": "이관제", "password": "pw-12345678", "role": "controller"})
    C = {"Authorization": "Bearer " + client.post("/v1/auth/login", json={"login_id": "ctl.lee", "password": "pw-12345678"}).json()["token"]}
    assert client.get("/v1/admin/rbac", headers=C).status_code == 403
    assert _put(client, C, diagnose=["admin"]).status_code == 403
    assert _put(client, _user(client), diagnose=["admin"]).status_code == 403


def test_whoami_permissions_admin_key_has_all(client):
    """관리자 키(세션 없음)도 whoami 로 유효 권한을 받는다 — 운영 관리자 열은 잠겨 모두 허용."""
    from cv_api.rbac import PERMISSIONS
    assert set(client.get("/v1/auth/whoami", headers=ADMIN).json()["permissions"]) == set(PERMISSIONS)
