"""서버 분리 — 진단 API(9544)와 웹 백엔드(9524)가 경로를 겹치지 않게 나눠 갖고, 합치면 전체 계약과 같다."""
from __future__ import annotations

from cv_api.app import create_app
from cv_api.services import guide

MODEL_ADMIN = ("/v1/admin/integrations", "/v1/admin/detector")


def _paths(role: str) -> set:
    return set(create_app(role).openapi()["paths"])


def test_roles_partition_all_paths():
    api, web, all_ = _paths("api"), _paths("web"), _paths("all")
    assert api.isdisjoint(web)
    assert api | web == all_


def test_api_owns_diagnosis_and_model_admin():
    api = _paths("api")
    for p in ("/v1/diagnose", "/v1/diagnose/batch", "/v1/measurements", "/v1/next-vehicle", "/v1/readiness", "/v1/api-guide",
              "/v1/admin/integrations", "/v1/admin/detector", "/v1/admin/detector/preload"):
        assert p in api, p


def test_web_owns_db_admin_and_web_media():
    web = _paths("web")
    assert all((p.startswith("/v1/admin/") and not p.startswith(MODEL_ADMIN)) or p.startswith("/v1/web/") for p in web)
    for p in ("/v1/web/diagnose", "/v1/web/diagnose-video", "/v1/web/measurements"):
        assert p in web, p
    for p in ("/v1/admin/cameras", "/v1/admin/cameras/{camera_id}/roi", "/v1/admin/policies/threshold", "/v1/admin/verification-runs",
              "/v1/admin/ops-status"):
        assert p in web, p


def test_catalog_matches_combined_contract(fresh_db):
    assert guide.verify_and_publish(create_app("all").openapi())["status"] == "published"


def test_web_readiness_reads_db_when_no_detector_in_process(stub, monkeypatch):
    """웹 백엔드 프로세스에는 검출기가 없다 — ops-status 의 적재 상태는 진단 API 가 남긴 DB 기록에서 온다."""
    from fastapi.testclient import TestClient
    from cv_api.services import ops
    from tests.helpers import ADMIN

    monkeypatch.setattr(ops.runtime, "detector", None)
    with TestClient(create_app("web")) as c:
        r = c.get("/v1/admin/ops-status", headers=ADMIN)
    assert r.status_code == 200
    det = r.json()["readiness"]["detector"]
    assert r.json()["readiness"]["readiness"] == "ready"
    assert det["kind"] == "stub" and det["loaded"] is True
