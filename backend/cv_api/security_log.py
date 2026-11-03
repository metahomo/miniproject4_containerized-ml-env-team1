"""보안 로그 — 계정 잠금·관리자 해제만 남긴다 (2026-11-02 사용자 결정). 비밀번호·키·클라이언트 IP 는 남기지 않는다.

표준 출력(앱 로그)에 항상 남기고, SECURITY_LOG_PATH 가 있으면 파일에도 남긴다.
도커는 /data 볼륨에 두어 컨테이너를 다시 만들어도 남는다. 파일을 쓸 수 없어도 로그인·해제는 막지 않는다.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .settings import get_settings

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

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
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(_handler)


def event(message: str) -> None:
    _use_path(get_settings().SECURITY_LOG_PATH)
    log.info(message)
