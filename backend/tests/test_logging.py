"""운영 로그 파일 — app.log·error.log·security.log 분류, 비밀값 가리기, 파일 교체, 쓰기 실패 (2026-11-03)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cv_api import log_setup, security_log
from cv_api.app import create_app
from cv_api.gates import GateBlocked
from cv_api.services import policy
from cv_api.settings import get_settings
from tests.conftest import _noop_lifespan
from tests.helpers import ADMIN, KEY

USER = {"login_id": "dev.kim", "name": "김개발", "password": "pw-12345678"}


def _reset():
    log_setup.configure("")
    get_settings.cache_clear()
    security_log.event("close test handler")


@pytest.fixture()
def logs(stub, tmp_path, monkeypatch):
    folder = tmp_path / "logs"
    monkeypatch.setenv("LOG_DIR", str(folder))
    monkeypatch.setenv("SECURITY_LOG_PATH", str(folder / "security.log"))
    get_settings.cache_clear()
    yield folder
    monkeypatch.delenv("LOG_DIR")
    monkeypatch.delenv("SECURITY_LOG_PATH")
    _reset()


@pytest.fixture()
def web(logs):
    app = create_app()
    app.router.lifespan_context = _noop_lifespan

    @app.get("/v1/test/boom")
    def boom():
        raise RuntimeError("upstream https://x/api?serviceKey=SECRET-BIS&a=1 postgresql://u:SECRET-DB@db/cv [parameters: {'h': 'SECRET-HASH'}]")

    @app.get("/v1/test/not-ready")
    def not_ready():
        raise GateBlocked("G0", "NOT_READY", "준비 중", "operator", 503)

    @app.get("/v1/test/bad-input")
    def bad_input():
        raise GateBlocked("G2", "BAD_INPUT", "값 오류", "self", 422)

    @app.get("/v1/test/operator-block")
    def operator_block():
        raise GateBlocked("G3", "CAMERA_NOT_FOUND", "없는 카메라", "operator", 404)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _read(folder: Path, name: str) -> str:
    path = folder / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_normal_request_only_in_app_log(web, logs):
    r = web.get("/v1/readiness")
    rid = r.headers["X-Request-ID"]
    line = next(l for l in _read(logs, "app.log").splitlines() if rid in l)
    assert "method=GET path=/v1/readiness status=200 reason_code=- caller=-" in line and "dur_ms=" in line and "model_version=" in line
    assert rid not in _read(logs, "error.log") and rid not in _read(logs, "security.log")


def test_caller_is_recorded(web, logs):
    rid = web.get("/v1/admin/accounts", headers=ADMIN).headers["X-Request-ID"]
    assert f"req_id={rid} method=GET path=/v1/admin/accounts status=200 reason_code=- caller=op1" in _read(logs, "app.log")


def test_key_rejections_go_to_security_not_error(web, logs):
    cases = [({}, 401, "AUTH_MISSING"), ({"X-API-Key": "SECRET-API"}, 403, "AUTH_INVALID"), ({"X-Admin-Key": "SECRET-ADMIN"}, 403, "ADMIN_INVALID")]
    for headers, status, reason in cases:
        r = web.get("/v1/admin/accounts", headers=headers)
        assert r.status_code == status and r.json()["reason_code"] == reason
        rid = r.headers["X-Request-ID"]
        assert f"key_rejected req_id={rid} method=GET path=/v1/admin/accounts status={status} reason_code={reason}" in _read(logs, "security.log")
        assert _read(logs, "app.log").count(rid) == 1     # 요청 로그 한 줄만
        assert rid not in _read(logs, "error.log")
    joined = "".join(_read(logs, n) for n in ("app.log", "error.log", "security.log"))
    assert "SECRET" not in joined


def test_login_failure_in_app_log_without_values(web, logs):
    web.post("/v1/auth/signup", json=USER)
    assert web.post("/v1/auth/login", json={"login_id": "dev.kim", "password": "SECRET-TYPED"}).status_code == 401
    assert web.post("/v1/auth/login", json={"login_id": "SECRET-ID", "password": "x"}).status_code == 401
    app = _read(logs, "app.log")
    assert "login_failed login_id=dev.kim" in app and "login_failed login_id=(없는 아이디)" in app
    assert "secret" not in (app + _read(logs, "error.log")).lower()
    assert "login_failed" not in _read(logs, "security.log")


def test_lock_and_unlock_in_app_and_security(web, logs):
    web.post("/v1/auth/signup", json=USER)
    for _ in range(5):
        web.post("/v1/auth/login", json={"login_id": "dev.kim", "password": "wrong"})
    for name in ("app.log", "security.log"):
        assert "login_locked login_id=dev.kim" in _read(logs, name)
    assert "login_locked" not in _read(logs, "error.log")


def test_unhandled_error_has_trace_only_in_error_log_and_is_redacted(web, logs):
    r = web.get("/v1/test/boom")
    assert r.status_code == 500
    rid = next(l for l in _read(logs, "app.log").splitlines() if "/v1/test/boom" in l).split("req_id=")[1].split()[0]
    app, err = _read(logs, "app.log"), _read(logs, "error.log")
    assert f"req_id={rid} method=GET path=/v1/test/boom status=500" in err
    assert "Traceback" in err and "RuntimeError" in err and "serviceKey=***" in err
    assert "Traceback" not in app
    assert "SECRET" not in app + err


def test_503_goes_to_error_with_reason(web, logs):
    rid = web.get("/v1/test/not-ready").headers["X-Request-ID"]
    err = _read(logs, "error.log")
    assert f"req_id={rid} method=GET path=/v1/test/not-ready status=503 reason_code=NOT_READY" in err and "Traceback" not in err
    assert f"req_id={rid}" in _read(logs, "app.log") and rid not in _read(logs, "security.log")


def test_operator_block_goes_to_error_self_block_does_not(web, logs):
    operator_rid = web.get("/v1/test/operator-block").headers["X-Request-ID"]
    self_rid = web.get("/v1/test/bad-input").headers["X-Request-ID"]
    err, app = _read(logs, "error.log"), _read(logs, "app.log")
    assert f"req_id={operator_rid} method=GET path=/v1/test/operator-block status=404 reason_code=CAMERA_NOT_FOUND" in err
    assert self_rid not in err
    assert operator_rid in app and self_rid in app


def test_permission_denied_is_not_a_failure_or_key_rejection(web, logs):
    r = web.get("/v1/admin/accounts", headers=KEY)
    assert r.status_code == 401 and r.json()["reason_code"] == "ADMIN_REQUIRED"
    rid = r.headers["X-Request-ID"]
    assert rid in _read(logs, "app.log") and "caller=web" in _read(logs, "app.log")
    assert rid not in _read(logs, "error.log") and rid not in _read(logs, "security.log")


def test_slow_diagnose_goes_to_error_other_paths_do_not(logs, monkeypatch):
    monkeypatch.setenv("LOG_SLOW_MS", "-1")
    get_settings.cache_clear()
    app = create_app()
    app.router.lifespan_context = _noop_lifespan

    @app.get("/v1/test/diagnose-slow")
    def slow():
        return {}

    with TestClient(app) as c:
        slow_rid = c.get("/v1/test/diagnose-slow").headers["X-Request-ID"]
        other_rid = c.get("/v1/readiness").headers["X-Request-ID"]
    err = _read(logs, "error.log")
    assert f"req_id={slow_rid}" in err and "status=200" in err and "slow" in err
    assert other_rid not in err


def test_policy_change_in_app_log(web, logs):
    policy.set_demo(True, "op1")
    assert "policy_changed kind=validity demo_on=True by=op1" in _read(logs, "app.log")
    assert "policy_changed" not in _read(logs, "error.log")


def test_newline_in_path_cannot_forge_a_line(web, logs):
    assert log_setup.clean("a\r\nb\tc") == "a__b_c"
    web.get("/v1/x%0Aforged-line")
    assert not any(l.startswith("forged-line") for l in _read(logs, "app.log").splitlines())


def test_rotation_keeps_three_backups(tmp_path, monkeypatch):
    monkeypatch.setattr(log_setup, "MAX_BYTES", 500)
    log_setup.configure(str(tmp_path))
    try:
        for i in range(400):
            log_setup.logging.getLogger("cv_api.test").warning("rotation line %04d %s", i, "x" * 40)
    finally:
        log_setup.configure("")
    for name in ("app.log", "error.log"):
        assert {p.name for p in tmp_path.glob(name + "*")} == {name, f"{name}.1", f"{name}.2", f"{name}.3"}


def test_unwritable_log_dir_does_not_stop_service(stub, tmp_path, monkeypatch, caplog):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setenv("LOG_DIR", str(blocker / "logs"))
    get_settings.cache_clear()
    try:
        app = create_app()
        app.router.lifespan_context = _noop_lifespan
        with TestClient(app) as c:
            assert c.get("/v1/readiness").status_code == 200
        assert "log files unavailable" in caplog.text
    finally:
        monkeypatch.delenv("LOG_DIR")
        _reset()


def test_redact_patterns():
    text = log_setup.redact("a?ServiceKey=abc&b=1 mysql://u:pw@h/db Authorization: Bearer tok123 x-api-key: k1 [parameters: {'x': 1}]")
    assert "abc" not in text and ":pw@" not in text and "tok123" not in text and "k1" not in text and "'x'" not in text
