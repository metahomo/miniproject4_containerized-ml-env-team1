"""실행기 — 한 프로세스가 같은 앱(`create_app("all")`)을 배정 포트 두 개로 서비스한다 (2026-09-29 결정 D1).

    cd backend && python -m cv_api.serve            # 0.0.0.0:9544(진단 API·외부 연계) + 0.0.0.0:9524(웹 프론트 9504 의 프록시 대상)

두 포트는 경로·계약이 같다. 프로세스를 하나로 둔 이유: 검출기 적재·웜업, P0 운영 루프, server_instance 기록이
한 번만 일어나야 한다(두 프로세스면 모델이 두 번 적재되고 준비 상태 행이 둘이 된다). lifespan 은 첫 포트만 실행한다.
웹 변환 경로(/v1/web/*)는 DIAGNOSIS_API_URL(9544)로 중계하므로 같은 프로세스 안에서 그대로 동작한다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Sequence

import uvicorn

from .app import create_app
from .settings import Settings, get_settings


def build_servers(host: str, ports: Sequence[int], log_level: str = "info") -> List[uvicorn.Server]:
    app = create_app("all")
    return [
        uvicorn.Server(uvicorn.Config(app, host=host, port=p, log_level=log_level, lifespan="on" if i == 0 else "off",
                                      access_log=False))   # 기본 접근 로그는 클라이언트 IP 를 남긴다 → cv_api.access 한 줄로 대신 (API 점검 D6)
        for i, p in enumerate(ports)
    ]


async def _serve(servers: List[uvicorn.Server]) -> None:
    # 신호 처리는 첫 서버만 설치한다 — 종료하면 나머지도 내린다
    for srv in servers[1:]:
        srv.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    tasks = [asyncio.create_task(srv.serve()) for srv in servers]
    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for srv in servers:
        srv.should_exit = True
    await asyncio.gather(*tasks, return_exceptions=True)


def check_keys(s: Settings) -> None:
    """공개된 기본 키(changeme-…)로는 뜨지 않는다 — 0.0.0.0 으로 열리므로 누구나 운영 관리자가 된다 (BE-1).
    키가 비어 있어도 코드 기본값이 쓰이므로 여기서 함께 걸린다. 로컬 개발은 ALLOW_INSECURE_KEYS=1."""
    bad = s.insecure_key_fields()
    if bad and not s.ALLOW_INSECURE_KEYS:
        sys.exit(f"[cv_api.serve] 시작 거부: {', '.join(bad)} 에 공개된 기본 키(changeme-…)가 쓰이고 있다 (값이 비어도 기본값이 쓰인다).\n"
                 "  새 키를 만들어 backend/.env (도커는 docker.env) 에 '이름:sha256:<hex>' 로 넣는다:\n"
                 "  python -c \"import secrets,hashlib;k=secrets.token_urlsafe(24);print(k, 'sha256:'+hashlib.sha256(k.encode()).hexdigest())\"\n"
                 "  로컬 개발에서만 기본 키를 쓰려면 ALLOW_INSECURE_KEYS=1")


def main(argv: Sequence[str] | None = None) -> None:
    s = get_settings()
    check_keys(s)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--ports", default=",".join(str(p) for p in s.SERVE_PORTS), help="쉼표 구분. 첫 포트가 lifespan(모델 적재)을 맡는다")
    ap.add_argument("--log-level", default="info")
    a = ap.parse_args(argv)
    ports = [int(p) for p in a.ports.split(",") if p.strip()]
    asyncio.run(_serve(build_servers(a.host, ports, a.log_level)))


if __name__ == "__main__":
    main()
