"""T107·T108 — RBAC (유스케이스 액터 → 역할). 회원가입 → 바로 일반 사용자 로그인 → 키 신청 → 운영 관리자 승인 → 연계 시스템 호출, 역할별 허용·거부."""
from cv_api import db
from tests.helpers import ADMIN, KEY, make_frame

P = lambda x: (x, 260.0, x + 70.0, 620.0, 0.9)  # noqa: E731
USER = {"login_id": "dev.kim", "name": "김개발", "password": "pw-12345678", "org": "전광판 개발사"}


def _bearer(client, login_id, password):
    r = client.post("/v1/auth/login", json={"login_id": login_id, "password": password})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _diagnose(client, headers):
    return client.post("/v1/diagnose", headers=headers, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})


def test_signup_is_user_and_key_needs_approval(client, stub):
    r = client.post("/v1/auth/signup", json=USER)
    assert r.status_code == 201 and r.json()["account"]["status"] == "active" and r.json()["account"]["role"] == "user"
    assert "password_hash" not in r.json()["account"]
    # 가입하면 바로 로그인 — 일반 사용자는 기본 기능(조회·진단)을 로그인 세션으로 쓴다
    H = _bearer(client, "dev.kim", USER["password"])
    me = client.get("/v1/auth/me", headers=H).json()
    assert me["role"] == "user" and me["role_label"] == "일반 사용자"
    assert {"diagnose", "next_vehicle", "own_keys"} <= set(me["permissions"]) and "admin" not in me["permissions"]
    assert client.get("/v1/reference/cameras", headers=H).status_code == 200
    stub.boxes = [P(200)]
    assert _diagnose(client, H).status_code == 200
    # 키 신청 — 원문은 이때 한 번만, 승인 전에는 거부
    k = client.post("/v1/auth/keys", headers=H, json={"name": "정류장 전광판"}).json()
    assert k["key"].startswith("cvk_") and k["status"] == "pending" and "key_hash" not in k
    IK = {"X-API-Key": k["key"]}
    r = _diagnose(client, IK)
    assert r.status_code == 403 and r.json()["reason_code"] == "KEY_PENDING"
    # 운영 관리자가 승인 대기 목록에서 승인
    pend = client.get("/v1/admin/api-keys", headers=ADMIN, params={"status": "pending"}).json()
    assert [x["key_id"] for x in pend] == [k["key_id"]] and pend[0]["login_id"] == "dev.kim"
    r = client.patch(f"/v1/admin/api-keys/{k['key_id']}", headers=ADMIN, json={"status": "active"})
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["approved_by"] == "op1"
    assert client.get("/v1/admin/api-keys", headers=ADMIN, params={"status": "pending"}).json() == []
    # 승인된 키로 연계 시스템 호출 — 집계 기록의 호출 주체 = 계정:키이름
    assert client.get("/v1/auth/whoami", headers=IK).json()["role"] == "integration"
    assert _diagnose(client, IK).status_code == 200
    with db.connect() as conn:
        assert db.q1(conn, "SELECT caller_id FROM diagnosis_request ORDER BY request_id DESC LIMIT 1")["caller_id"] == "dev.kim:정류장 전광판"
    assert client.get("/v1/admin/cameras", headers=IK).status_code == 401      # 키로 관리 기능은 안 된다
    # 폐기하면 즉시 거부
    assert client.delete(f"/v1/auth/keys/{k['key_id']}", headers=H).status_code == 204
    r = _diagnose(client, IK)
    assert r.status_code == 403 and r.json()["reason_code"] == "AUTH_INVALID"
    assert client.patch(f"/v1/admin/api-keys/{k['key_id']}", headers=ADMIN, json={"status": "active"}).status_code == 409


def test_rejected_key_and_admin_self_key(client):
    client.post("/v1/auth/signup", json=USER)
    H = _bearer(client, "dev.kim", USER["password"])
    k = client.post("/v1/auth/keys", headers=H, json={"name": "앱"}).json()
    client.patch(f"/v1/admin/api-keys/{k['key_id']}", headers=ADMIN, json={"status": "rejected"})
    r = client.get("/v1/reference/cameras", headers={"X-API-Key": k["key"]})
    assert r.status_code == 403 and r.json()["reason_code"] == "KEY_REJECTED"
    # 운영 관리자 본인의 신청은 바로 승인
    client.post("/v1/admin/accounts", headers=ADMIN, json={"login_id": "ops.park", "name": "박운영", "password": "pw-12345678", "role": "admin"})
    A = _bearer(client, "ops.park", "pw-12345678")
    ak = client.post("/v1/auth/keys", headers=A, json={"name": "운영 점검"}).json()
    assert ak["status"] == "active" and ak["approved_by"] == "ops.park"
    assert client.get("/v1/reference/cameras", headers={"X-API-Key": ak["key"]}).status_code == 200


def test_login_required_and_role_permissions(client):
    # 로그인·키 없이는 기본 기능도 안 된다 (공개는 가입·로그인·준비 상태·API 안내)
    r = client.get("/v1/reference/cameras")
    assert r.status_code == 401 and r.json()["reason_code"] == "AUTH_MISSING"
    assert client.get("/v1/readiness").status_code == 200 and client.get("/v1/api-guide").status_code == 200
    # 운영 관리자가 관제 담당자 계정을 만든다 (바로 사용)
    r = client.post("/v1/admin/accounts", headers=ADMIN, json={"login_id": "ctl.lee", "name": "이관제", "password": "pw-12345678", "role": "controller"})
    assert r.status_code == 201 and r.json()["status"] == "active"
    C = _bearer(client, "ctl.lee", "pw-12345678")
    for path in ("/v1/admin/gate-events", "/v1/admin/quality-metrics", "/v1/admin/ops-status", "/v1/admin/cameras"):
        assert client.get(path, headers=C).status_code == 200, path          # 관제 뷰 읽기
    r = client.get("/v1/admin/policies/threshold", headers=C)
    assert r.status_code == 403 and r.json()["reason_code"] == "ROLE_FORBIDDEN"   # 정책은 운영 관리자만
    assert client.post("/v1/admin/cameras", headers=C, json={"camera_id": "X1", "place_type": "bus_in"}).status_code == 403
    assert client.post("/v1/auth/keys", headers=C, json={"name": "x"}).status_code == 403   # 키 신청은 일반 사용자·운영 관리자
    # 일반 사용자는 관리·관제 경로, 키 승인 모두 거부
    client.post("/v1/auth/signup", json=USER)
    U = _bearer(client, "dev.kim", USER["password"])
    assert client.get("/v1/admin/gate-events", headers=U).status_code == 403
    assert client.get("/v1/admin/api-keys", headers=U).status_code == 403
    # 운영 관리자 계정(세션)은 관리 기능 가능 — 관리자 키 없이
    client.post("/v1/admin/accounts", headers=ADMIN, json={"login_id": "ops.park", "name": "박운영", "password": "pw-12345678", "role": "admin"})
    A = _bearer(client, "ops.park", "pw-12345678")
    assert client.get("/v1/admin/policies/threshold", headers=A).status_code == 200
    assert client.get("/v1/admin/accounts", headers=A).status_code == 200
    # 서버 설정의 호출 키(서버 간·스크립트)는 그대로
    assert client.get("/v1/reference/cameras", headers=KEY).status_code == 200


def test_disable_cuts_session_and_keys(client):
    aid = client.post("/v1/auth/signup", json=USER).json()["account"]["account_id"]
    H = _bearer(client, "dev.kim", USER["password"])
    k = client.post("/v1/auth/keys", headers=H, json={"name": "앱"}).json()
    client.patch(f"/v1/admin/api-keys/{k['key_id']}", headers=ADMIN, json={"status": "active"})
    assert client.get("/v1/reference/cameras", headers={"X-API-Key": k["key"]}).status_code == 200
    client.patch(f"/v1/admin/accounts/{aid}", headers=ADMIN, json={"status": "disabled"})
    r = client.get("/v1/auth/me", headers=H)
    assert r.status_code == 401 and r.json()["reason_code"] == "SESSION_INVALID"
    assert client.get("/v1/reference/cameras", headers={"X-API-Key": k["key"]}).status_code == 403
    r = client.post("/v1/auth/login", json={"login_id": "dev.kim", "password": USER["password"]})
    assert r.status_code == 403 and r.json()["reason_code"] == "ACCOUNT_DISABLED"


def test_signup_validation_and_login_failure(client):
    assert client.post("/v1/auth/signup", json={**USER, "password": "short"}).status_code == 422
    assert client.post("/v1/auth/signup", json={**USER, "login_id": "한글아이디"}).status_code == 422
    assert client.post("/v1/auth/signup", json=USER).status_code == 201
    r = client.post("/v1/auth/signup", json=USER)
    assert r.status_code == 422 and r.json()["reason_code"] == "LOGIN_ID_TAKEN"
    r = client.post("/v1/auth/login", json={"login_id": "dev.kim", "password": "wrong-password"})
    assert r.status_code == 401 and r.json()["reason_code"] == "LOGIN_FAILED"
    assert client.get("/v1/auth/keys").status_code == 401                         # 인증 없음
    m = client.get("/v1/auth/roles").json()
    assert m["roles"]["user"] == "일반 사용자" and "developer" not in m["roles"]
    assert any(p["permission"] == "control_view" for p in m["permissions"])
