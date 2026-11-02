"""D1(2026-09-29) — 한 프로세스가 같은 전체 앱을 두 포트(9544·9524)로 연다. 모델 적재(lifespan)는 첫 포트만."""
import hashlib

import pytest

from cv_api import app as app_module
from cv_api.serve import build_servers, check_keys
from cv_api.settings import Settings


def test_two_ports_share_one_full_app():
    a, b = build_servers("127.0.0.1", [9544, 9524])
    assert a.config.app is b.config.app
    assert (a.config.port, b.config.port) == (9544, 9524)
    assert (a.config.lifespan, b.config.lifespan) == ("on", "off")
    paths = set(a.config.app.openapi()["paths"])
    assert {"/v1/diagnose", "/v1/next-vehicle", "/v1/admin/cameras", "/v1/web/diagnose", "/v1/admin/detector"} <= paths


def test_defaults():
    assert Settings().SERVE_PORTS == (9544, 9524)
    assert "/v1/admin/cameras" in app_module.app.openapi()["paths"]   # uvicorn cv_api.app:app 도 전체 앱


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_public_default_keys_refuse_start():
    """BE-1: 공개된 기본 키(값이 비어 기본값이 쓰일 때 포함)로는 운영 실행이 뜨지 않는다."""
    s = _settings(API_KEYS="web:changeme-web", ADMIN_KEYS="op1:changeme-admin")
    assert s.insecure_key_fields() == ("API_KEYS", "ADMIN_KEYS")
    with pytest.raises(SystemExit) as e:
        check_keys(s)
    assert "API_KEYS, ADMIN_KEYS" in str(e.value)
    weak_hash = "sha256:" + hashlib.sha256(b"changeme-admin").hexdigest()
    assert _settings(API_KEYS="web:fresh-web-key", ADMIN_KEYS=f"op1:{weak_hash}").insecure_key_fields() == ("ADMIN_KEYS",)


def test_fresh_keys_or_dev_opt_in_start():
    check_keys(_settings(API_KEYS="web:fresh-web-key", ADMIN_KEYS="op1:fresh-admin-key"))
    check_keys(_settings(API_KEYS="web:changeme-web", ADMIN_KEYS="op1:changeme-admin", ALLOW_INSECURE_KEYS=True))
