"""스크립트 공용 httpx 클라이언트.

D1(2026-09-29) 이후 9524·9544 는 같은 전체 앱이라 어느 포트로 보내도 된다. 경로 분배(/v1/admin/*·/v1/web/* → 9524, 그 밖 → 9544)는
분리 구성(cv_api/web.py 주석)으로 되돌릴 때를 위해 남긴다 — 두 포트 모두 전체 앱이면 결과가 같다.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

API_BASE = "http://localhost:9544"
WEB_BASE = "http://localhost:9524"
_MODEL_ADMIN = ("/v1/admin/integrations", "/v1/admin/detector")
_ADMIN_KEY_FILE = Path(__file__).resolve().parent.parent / "backend" / ".logs" / "ADMIN_KEY.txt"


def env_keys() -> tuple:
    """(API 키, 관리자 키). 명령행 인자로 받지 않는다 — ps 로 다른 사용자에게 보인다 (API 점검 D8).
    API 키 = 환경변수 CV_API_KEY · 관리자 키 = CV_ADMIN_KEY → 키 파일 CV_KEY_FILE(기본 backend/.logs/ADMIN_KEY.txt, 권한 600). 없으면 로컬 개발용 기본값."""
    api = os.environ.get("CV_API_KEY", "changeme-web")
    admin = os.environ.get("CV_ADMIN_KEY", "")
    f = Path(os.environ.get("CV_KEY_FILE", _ADMIN_KEY_FILE))
    if not admin and f.is_file():
        admin = next((l.split("=", 1)[1].strip() for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("ADMIN_KEY=")), "")
    return api, admin or "changeme-admin"


def is_web_path(path: str) -> bool:
    return path.startswith("/v1/web") or (path.startswith("/v1/admin") and not path.startswith(_MODEL_ADMIN))


class SplitClient:
    def __init__(self, api_base: str = API_BASE, web_base: str = WEB_BASE, **kw):
        self.api = httpx.Client(base_url=api_base, **kw)
        self.web = httpx.Client(base_url=web_base, **kw)

    def _c(self, path: str) -> httpx.Client:
        return self.web if is_web_path(path) else self.api

    def get(self, path: str, **kw) -> httpx.Response:
        return self._c(path).get(path, **kw)

    def post(self, path: str, **kw) -> httpx.Response:
        return self._c(path).post(path, **kw)

    def delete(self, path: str, **kw) -> httpx.Response:
        return self._c(path).delete(path, **kw)
