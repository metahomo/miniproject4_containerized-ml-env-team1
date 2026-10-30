"""2026-09-30 (SD_03 §16 17) — 계정 역할·상태 변경 이력: 누가 언제 무엇을 바꿨는지."""
from tests.helpers import ADMIN


def test_role_and_status_changes_are_logged(client):
    a = client.post("/v1/admin/accounts", headers=ADMIN, json={"login_id": "ctl.kim", "name": "김관제", "password": "pw-12345678", "role": "controller"}).json()
    aid = a["account_id"]
    client.patch(f"/v1/admin/accounts/{aid}", headers=ADMIN, json={"role": "admin"})
    client.patch(f"/v1/admin/accounts/{aid}", headers=ADMIN, json={"role": "admin"})          # 같은 값 — 이력 안 남김
    client.patch(f"/v1/admin/accounts/{aid}", headers=ADMIN, json={"status": "disabled"})
    rows = client.get(f"/v1/admin/accounts/{aid}/changes", headers=ADMIN).json()
    got = [(r["field"], r["old_value"], r["new_value"]) for r in rows]
    assert got[:2] == [("status", "active", "disabled"), ("role", "controller", "admin")]
    assert ("role", None, "controller") in got and ("status", None, "active") in got               # 생성 때
    assert all(r["changed_by"] for r in rows) and len(rows) == 4


def test_signup_logged_as_signup_and_unknown_account_404(client):
    client.post("/v1/auth/signup", json={"login_id": "user.one", "name": "일반", "password": "pw-12345678"})
    acc = [x for x in client.get("/v1/admin/accounts", headers=ADMIN).json() if x["login_id"] == "user.one"][0]
    rows = client.get(f"/v1/admin/accounts/{acc['account_id']}/changes", headers=ADMIN).json()
    assert {r["changed_by"] for r in rows} == {"signup"}
    assert client.get("/v1/admin/accounts/99999/changes", headers=ADMIN).status_code == 404
