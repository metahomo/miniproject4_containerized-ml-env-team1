"""보안 로그 — 계정 잠금·관리자 해제, 키 없는 요청·잘못된 키 (2026-11-03 사용자 결정). 비밀번호·키·클라이언트 IP 는 남기지 않는다.

표준 출력(앱 로그)에 항상 남기고, 파일에도 남긴다. 파일 위치는 SECURITY_LOG_PATH, 비어 있으면 LOG_DIR/security.log, 둘 다 비면 파일을 만들지 않는다.
도커는 /data 볼륨에 두어 컨테이너를 다시 만들어도 남는다. 파일을 쓸 수 없어도 로그인·해제는 막지 않는다.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .log_setup import BACKUP_COUNT, MAX_BYTES, SafeFormatter
from .settings import get_settings

log = logging.getLogger("cv_api.security")
log.setLevel(logging.INFO)
_handler: Optional[logging.Handler] = None
_path = ""


def _use_path(path: str) -> None:
    global _handler, _path
    if path == _path:
        return
    if _handler is not None:
        log.removeHandler(_handler)
        _handler.close()
        _handler = None
    _path = path
    if not path:
        return
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    except OSError as e:
        log.warning("security log file unavailable: %s", e)
        return
    _handler.setFormatter(SafeFormatter("%(asctime)s %(message)s"))
    log.addHandler(_handler)


def _file_path() -> str:
    s = get_settings()
    if s.SECURITY_LOG_PATH:
        return s.SECURITY_LOG_PATH
    return str(Path(s.LOG_DIR) / "security.log") if s.LOG_DIR else ""


def event(message: str, to_app: bool = True) -> None:
    """to_app=False: 요청 로그 한 줄이 이미 app.log 에 남는 경우 — 같은 요청을 두 줄로 남기지 않는다."""
    _use_path(_file_path())
    log.info(message, extra={"skip_app": not to_app})
