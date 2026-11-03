"""로그인 시도 제한 — 15분 안에 5번 실패하면 15분 잠금, 자동 해제, 관리자 해제, 보안 로그 (2026-11-02)."""
import logging

from sqlalchemy import text

from cv_api import db, security_log
from cv_api.settings import get_settings
from tests.helpers import ADMIN

USER = {"login_id": "dev.kim", "name": "김개발", "password": "pw-12345678"}
PAST = "2020-01-01T00:00:00"


def _login(client, password="wrong-password", login_id="dev.kim"):
    return client.post("/v1/auth/login", json={"login_id": login_id, "password": password})


def _fail(client, times, login_id="dev.kim"):
    return [_login(client, login_id=login_id).status_code for _ in range(times)]


def _attempt(login_id="dev.kim"):
    with db.connect() as conn:
        return db.q1(conn, "SELECT * FROM login_attempt WHERE login_id=:l", l=login_id)


def _set(column, value, login_id="dev.kim"):
    with db.connect() as conn:
        conn.execute(text(f"UPDATE login_attempt SET {column}=:v WHERE login_id=:l"), {"v": value, "l": login_id})


def _account(client, login_id="dev.kim"):
    return [a for a in client.get("/v1/admin/accounts", headers=ADMIN).json() if a["login_id"] == login_id][0]


def test_fifth_failure_locks_even_correct_password(client):
    client.post("/v1/auth/signup", json=USER)
    assert _fail(client, 4) == [401, 401, 401, 401]
    r = _login(client)
    assert r.status_code == 429 and r.json()["reason_code"] == "LOGIN_LOCKED"
    assert _attempt()["fail_count"] == 5 and _attempt()["locked_until"]
    r = _login(client, USER["password"])
    assert r.status_code == 429 and r.json()["reason_code"] == "LOGIN_LOCKED"


def test_success_resets_failures(client):
    client.post("/v1/auth/signup", json=USER)
    _fail(client, 4)
    assert _login(client, USER["password"]).status_code == 200
    assert _attempt() is None
    assert _fail(client, 4) == [401, 401, 401, 401]
    assert _login(client, USER["password"]).status_code == 200


def test_lock_expires_and_count_restarts(client):
    client.post("/v1/auth/signup", json=USER)
    _fail(client, 5)
    first_until = _attempt()["locked_until"]
    assert first_until > db.now_iso()
    _set("locked_until", PAST)
    assert _account(client)["locked_until"] is None
    assert _login(client).status_code == 401            # 풀린 뒤 첫 실패는 다시 1번째
    assert _attempt()["fail_count"] == 1 and _attempt()["locked_until"] is None
    assert _login(client, USER["password"]).status_code == 200


def test_failures_outside_window_are_not_counted(client):
    client.post("/v1/auth/signup", json=USER)
    _fail(client, 4)
    _set("first_failed_at", PAST)
    assert _login(client).status_code == 401
    assert _attempt()["fail_count"] == 1


def test_failures_inside_lock_do_not_extend_it(client):
    client.post("/v1/auth/signup", json=USER)
    _fail(client, 5)
    before = _attempt()
    assert _login(client).status_code == 429
    assert _attempt() == before


def test_unknown_id_gets_same_responses(client):
    client.post("/v1/auth/signup", json=USER)
    known = [_login(client) for _ in range(5)]
    unknown = [_login(client, login_id="no.such.user") for _ in range(5)]
    assert [r.status_code for r in unknown] == [r.status_code for r in known]
    assert unknown[0].json() == known[0].json() and unknown[-1].json() == known[-1].json()


def test_login_id_case_and_space_share_a_count(client):
    client.post("/v1/auth/signup", json=USER)
    for lid in ("dev.kim", "DEV.KIM", " dev.kim ", "Dev.Kim"):
        assert _login(client, login_id=lid).status_code == 401
    assert _attempt()["fail_count"] == 4


def test_expired_rows_are_cleaned(client):
    _fail(client, 1, login_id="gone.a")
    _fail(client, 5, login_id="gone.b")
    _set("first_failed_at", PAST, "gone.a")
    _set("locked_until", PAST, "gone.b")
    _fail(client, 1, login_id="other")
    assert _attempt("gone.a") is None and _attempt("gone.b") is None and _attempt("other")["fail_count"] == 1


def test_admin_unlock(client):
    client.post("/v1/auth/signup", json=USER)
    _fail(client, 5)
    acc = _account(client)
    assert acc["locked_until"] and "password_hash" not in acc
    r = client.post(f"/v1/admin/accounts/{acc['account_id']}/unlock", headers=ADMIN)
    assert r.status_code == 200 and r.json()["locked_until"] is None and "password_hash" not in r.json()
    assert _attempt() is None and _account(client)["locked_until"] is None
    assert _login(client, USER["password"]).status_code == 200


def test_unlock_requires_admin_and_account(client):
    client.post("/v1/auth/signup", json=USER)
    _fail(client, 5)
    aid = _account(client)["account_id"]
    assert client.post(f"/v1/admin/accounts/{aid}/unlock").status_code == 401
    client.post("/v1/auth/signup", json={**USER, "login_id": "other.user"})
    token = _login(client, USER["password"], "other.user").json()["token"]
    r = client.post(f"/v1/admin/accounts/{aid}/unlock", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert _attempt()["locked_until"]
    assert client.post("/v1/admin/accounts/99999/unlock", headers=ADMIN).status_code == 404


def test_disabled_account_keeps_its_response(client):
    client.post("/v1/auth/signup", json=USER)
    aid = _account(client)["account_id"]
    client.patch(f"/v1/admin/accounts/{aid}", headers=ADMIN, json={"status": "disabled"})
    r = _login(client, USER["password"])
    assert r.status_code == 403 and r.json()["reason_code"] == "ACCOUNT_DISABLED"


def test_settings_change_limits(client, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FAILS", "2")
    get_settings.cache_clear()
    client.post("/v1/auth/signup", json=USER)
    assert _fail(client, 2) == [401, 429]


def test_security_log_file(client, tmp_path, monkeypatch):
    path = tmp_path / "logs" / "security.log"
    monkeypatch.setenv("SECURITY_LOG_PATH", str(path))
    get_settings.cache_clear()
    try:
        client.post("/v1/auth/signup", json=USER)
        _fail(client, 5)
        _fail(client, 5, login_id="typed-a-secret")
        aid = _account(client)["account_id"]
        client.post(f"/v1/admin/accounts/{aid}/unlock", headers=ADMIN)
        client.post(f"/v1/admin/accounts/{aid}/unlock", headers=ADMIN)     # 잠겨 있지 않으면 기록 없음
        lines = path.read_text(encoding="utf-8").splitlines()
    finally:
        monkeypatch.delenv("SECURITY_LOG_PATH")
        get_settings.cache_clear()
        security_log.event("close test handler")
    assert len(lines) == 3
    assert "login_locked login_id=dev.kim" in lines[0]
    assert "login_locked login_id=(없는 아이디)" in lines[1]
    assert "login_unlocked login_id=dev.kim by=" in lines[2]
    text_ = "\n".join(lines)
    assert "wrong-password" not in text_ and "typed-a-secret" not in text_


def test_unwritable_log_file_does_not_block_login(client, tmp_path, monkeypatch, caplog):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setenv("SECURITY_LOG_PATH", str(blocker / "security.log"))
    get_settings.cache_clear()
    client.post("/v1/auth/signup", json=USER)
    with caplog.at_level(logging.WARNING, logger="cv_api.security"):
        assert _fail(client, 5)[-1] == 429
    assert "security log file unavailable" in caplog.text
    monkeypatch.delenv("SECURITY_LOG_PATH")
    get_settings.cache_clear()
    security_log.event("reset test handler")
