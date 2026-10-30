"""(보존) 웹 백엔드만 따로 띄우는 진입점 — 2026-09-29 결정 D1 이후 기본 실행은 `python -m cv_api.serve`(한 프로세스, 두 포트, 전체 앱).
분리 구성(9524 = 관리·웹 변환, 9544 = 진단 계열)이 다시 필요할 때만 쓴다 — 이때 9544 쪽은 `create_app("api")` 로 띄워야 경로가 겹치지 않는다."""
from __future__ import annotations

from .app import create_app

app = create_app("web")
