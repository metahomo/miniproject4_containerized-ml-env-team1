"""FastAPI 앱 — 한 프로세스가 같은 전체 앱(`create_app("all")`)을 9544·9524 두 포트로 서비스한다 (2026-09-29 결정 D1).
실행: `python -m cv_api.serve` (cv_api/serve.py). 9544 = 외부 연계용 공개 API, 9524 = 웹 프론트(9504) 프록시 대상. 계약은 같다.

아래 역할("api"·"web")은 라우터 묶음 구분으로만 남긴다(2026-09-29 오전의 두 서버 분리 구성, 테스트가 경로 분할을 확인):
- 진단 API (`cv_api.app:app`, 9544): 연계 시스템·웹 화면이 부르는 진단 계열 + 모델이 필요한 관리 기능(연동·검출기 적재).
  lifespan: DDL 적용 → 인스턴스 preparing → 검출기 적재·웜업·계약 확인 → ready → P0 루프.
  기동 중에도 요청을 받되 G0 가 닫혀 진단 계열은 503 이고, /v1/readiness 와 /v1/api-guide 는 열려 있다(UC15 E1).
- 웹 백엔드 (`cv_api.web:app`, 9524): 웹 화면의 운영 관리 기능 `/v1/admin/*` (기준 정보·정책·검증 판정·운영 상태)와
  웹 화면 제출 경로 `/v1/web/*` (규격 밖 사진·영상을 변환해 진단 API 로 넘김, media.py). 모델을 적재하지 않는다.
  lifespan: DDL 적용만. 준비 상태는 DB(v_readiness)에서 읽는다.

두 서버는 같은 DB 를 공유한다. `create_app("all")` 은 한 프로세스에 전부 올린다(테스트·단일 프로세스 개발용).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from . import __version__
from .gates import GateBlocked, gate_exception_handler
from .services import ops
from .settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cv_api")
access_log = logging.getLogger("cv_api.access")
logging.getLogger("httpx").setLevel(logging.WARNING)   # httpx INFO 는 요청 URL 전체를 남긴다 — BIS 인증키(serviceKey)가 로그에 새지 않게

Role = Literal["api", "web", "all"]


def routers_for(role: Role) -> list[APIRouter]:
    from .routers import accounts, admin, admin_model, diagnose, gate_events, guide, measurements, next_vehicle, readiness, reference_public, web_media

    api = [readiness.router, diagnose.router, measurements.router, next_vehicle.router, gate_events.router, guide.router, admin_model.router, reference_public.router, accounts.auth_router, accounts.admin_router]
    web = [admin.router, web_media.router]
    return {"api": api, "web": web, "all": api + web}[role]


def _api_lifespan(role: Role):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        s = get_settings()
        loop = asyncio.get_running_loop()

        # 적재는 블로킹이므로 스레드에서 — 그동안 readiness=preparing 으로 응답한다 (로딩 시간 노출)
        def _start():
            out = ops.startup(s)
            try:
                from .services import guide
                # G17: 카탈로그 ↔ 실제 계약 대조 후 게시. 카탈로그는 두 서버의 경로를 모두 담으므로 합친 계약과 대조한다
                contract = app.openapi() if role == "all" else create_app("all").openapi()
                out["guide"] = guide.verify_and_publish(contract)
            except Exception as e:  # noqa: BLE001
                log.warning("guide publish failed: %s", e)
            return out

        app.state.startup_task = loop.run_in_executor(None, _start)
        app.state.ops_task = asyncio.create_task(ops.ops_loop(s))
        from .services import camera_power
        app.state.camera_task = asyncio.create_task(camera_power.scheduler_loop(s))   # S2b: 켜진 카메라 주기 자동 진단
        try:
            yield
        finally:
            app.state.ops_task.cancel()
            app.state.camera_task.cancel()
            # 적재 스레드가 종료 뒤에도 DB 에 쓰지 않게 끝날 때까지 기다린다 (최대 60초)
            await asyncio.wait({app.state.startup_task}, timeout=60)

    return lifespan


@asynccontextmanager
async def _web_lifespan(app: FastAPI):
    from . import db

    loop = asyncio.get_running_loop()
    app.state.startup_task = loop.run_in_executor(None, db.init_db)   # 멱등. 진단 API 와 동시에 떠도 안전 (db.apply_migrations)
    yield
    await asyncio.wait({app.state.startup_task}, timeout=30)


class PublicPrefix:
    """`https://p4.sumzip.com/API/...` 로 들어온 요청을 `/API` 를 뗀 경로로 처리하고 root_path 에 `/API` 를 둔다 (T098).
    웹 서버(9504) 프록시가 `/API/*` 를 그대로 9544 에 넘긴다. root_path 덕분에 Swagger(/API/docs)는 /API/openapi.json 을 읽고
    «Try it out» 도 /API/v1/... 로 호출한다. 접두사 없이 9544 에 바로 오는 요청(http://192.168.0.19:9544/docs)은 그대로다."""

    def __init__(self, app, prefix: str = "/API") -> None:
        self.app, self.prefix = app, prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path == self.prefix or path.startswith(self.prefix + "/"):
                scope = dict(scope)
                scope["root_path"] = scope.get("root_path", "") + self.prefix
                scope["path"] = path[len(self.prefix):] or "/"
                raw = scope.get("raw_path")
                if raw:
                    scope["raw_path"] = raw[len(self.prefix.encode()):] or b"/"
        await self.app(scope, receive, send)


def create_app(role: Role = "all") -> FastAPI:
    s = get_settings()
    title = {"api": "진단 API", "web": "웹 백엔드 (운영 관리)", "all": "진단 API + 웹 백엔드"}[role]
    lifespan = _web_lifespan if role == "web" else _api_lifespan(role)
    app = FastAPI(
        title=f"대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 — {title}",
        version=__version__,
        description="관제 영상 프레임 1장 → 잔여 탑승 가능 비율(%)·혼잡 등급·경고. 모든 응답은 통계적 추정치다. 카탈로그: /v1/api-guide",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=list(s.CORS_ORIGINS), allow_methods=["*"], allow_headers=["*"])
    app.add_exception_handler(GateBlocked, gate_exception_handler)
    app.add_middleware(PublicPrefix, prefix="/API")   # 공개 API 주소 https://p4.sumzip.com/API (T098)
    app.add_middleware(PublicPrefix, prefix="/model-api")   # 모델 게이트웨이 주소 https://p4.sumzip.com/model-api (API 점검 2026-09-30 A3 — /API 와 같은 앱)

    @app.middleware("http")
    async def _request_log(request: Request, call_next):
        """요청 번호표 (API 점검 D5·D6): X-Request-ID 헤더 + 로그 한 줄. 남기는 것 8필드 —
        req_id·path·status·dur_ms·input_len·label·score·model_version. 입력 원문·폼 값·키·클라이언트 IP 는 남기지 않는다."""
        req_id = uuid.uuid4().hex[:12]
        request.state.req_id = req_id
        t0 = time.perf_counter()
        status = 500
        try:
            resp = await call_next(request)
            status = resp.status_code
            resp.headers["X-Request-ID"] = req_id
            return resp
        finally:
            out = getattr(request.state, "log_result", None) or {}
            access_log.info("req_id=%s path=%s status=%s dur_ms=%.1f input_len=%s label=%s score=%s model_version=%s",
                            req_id, request.url.path, status, (time.perf_counter() - t0) * 1000,
                            request.headers.get("content-length", "-"), out.get("label", "-"), out.get("score", "-"),
                            out.get("model_version", "-"))
    for r in routers_for(role):
        app.include_router(r)

    @app.get("/", include_in_schema=False)
    def _root(request: Request) -> RedirectResponse:   # https://p4.sumzip.com/API → Swagger (T098)
        return RedirectResponse(url=request.scope.get("root_path", "") + "/docs")

    return app


app = create_app("all")   # `uvicorn cv_api.app:app --port 9544` 도 전체 앱. 두 포트는 cv_api.serve 로
