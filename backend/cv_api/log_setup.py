"""운영 로그 파일 — app.log(모든 요청·일반 이벤트)·error.log(장애) (2026-11-03 사용자 결정). 보안 기록은 security_log.

표준 출력은 그대로 두고, LOG_DIR 이 있으면 파일에도 남긴다. 도커는 /data 볼륨에 두어 컨테이너를 다시 만들어도 남는다.
파일을 쓸 수 없어도 서비스는 막지 않는다. 비밀값은 어느 로그에도 남기지 않는다 — 오류 메시지·스택 트레이스 안의 값은 SafeFormatter 가 가린다.
"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3
FILE_FORMAT = "%(asctime)s %(levelname)s %(message)s"

error_log = logging.getLogger("cv_api.error")   # 요청 단위 장애 한 줄 — error.log 전용(app.log 에는 요청 로그가 이미 있다)

KEY_REJECTED = {"AUTH_MISSING", "AUTH_INVALID", "ADMIN_INVALID", "KEY_PENDING"}   # security.log 로 가는 사유
OTHER_RESOLVER = {"operator", "external"}   # 호출자가 스스로 풀 수 없는 차단

_SECRETS = [
    (re.compile(r"(servicekey=)[^&\s'\"]+", re.I), r"\1***"),                         # BIS 인증키 (요청 URL)
    (re.compile(r"(://[^:/\s]+:)[^@/\s]+(@)"), r"\1***\2"),                           # DB 주소의 비밀번호
    (re.compile(r"(bearer\s+)\S+", re.I), r"\1***"),
    (re.compile(r"((?:x-api-key|x-admin-key)['\"]?\s*[:=]\s*['\"]?)[^'\"\s,}]+", re.I), r"\1***"),
    (re.compile(r"\[parameters: .*"), "[parameters: ***]"),                           # SQLAlchemy 오류의 바인딩 값 (해시·아이디 포함)
]
_CONTROL = re.compile(r"[\r\n\t]")

_handlers: List[logging.Handler] = []
_dir = ""


def redact(text: str) -> str:
    for pattern, repl in _SECRETS:
        text = pattern.sub(repl, text)
    return text


def clean(value: object) -> str:
    """요청에서 온 값(경로 등)의 줄바꿈을 지운다 — 로그 한 줄을 위조하지 못하게."""
    return _CONTROL.sub("_", str(value))


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class _NoTraceFormatter(SafeFormatter):
    """스택 트레이스는 error.log 에만 — app.log 는 한 줄로 유지한다."""

    def format(self, record: logging.LogRecord) -> str:
        saved = record.exc_info, record.exc_text, record.stack_info
        record.exc_info, record.exc_text, record.stack_info = None, None, None
        try:
            return super().format(record)
        finally:
            record.exc_info, record.exc_text, record.stack_info = saved


def _for_app(record: logging.LogRecord) -> bool:
    return record.name != error_log.name and not getattr(record, "skip_app", False)


def _for_error(record: logging.LogRecord) -> bool:
    return record.levelno >= logging.WARNING


def classify(status: int, reason_code: str, resolver_role: str, slow: bool) -> Optional[str]:
    """요청 한 건이 app.log 외에 어디로 가는지. security·error 는 겹치지 않는다."""
    if status in (401, 403):
        return "security" if reason_code in KEY_REJECTED else None
    if status >= 500 or slow or resolver_role in OTHER_RESOLVER:
        return "error"
    return None


def protect_stdout() -> None:
    """표준 출력에도 비밀값이 나가지 않게 한다."""
    for h in logging.getLogger().handlers:
        if type(h) is logging.StreamHandler:
            h.setFormatter(SafeFormatter(h.formatter._fmt if h.formatter else None))


def _file_handler(path: Path, level: int, keep, formatter: logging.Formatter) -> logging.Handler:
    h = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    h.setLevel(level)
    h.addFilter(keep)
    h.setFormatter(formatter)
    return h


def configure(log_dir: str) -> None:
    """같은 폴더로 다시 부르면 아무 일도 하지 않는다. 비우면 파일 기록을 끈다."""
    global _dir
    if log_dir == _dir:
        return
    root = logging.getLogger("cv_api")
    root.setLevel(logging.INFO)   # 전역 logging 설정이 이미 되어 있어도 요청 로그(INFO)가 걸러지지 않게
    for h in _handlers:
        root.removeHandler(h)
        h.close()
    _handlers.clear()
    _dir = log_dir
    if not log_dir:
        return
    try:
        folder = Path(log_dir)
        folder.mkdir(parents=True, exist_ok=True)
        _handlers.append(_file_handler(folder / "app.log", logging.INFO, _for_app, _NoTraceFormatter(FILE_FORMAT)))
        _handlers.append(_file_handler(folder / "error.log", logging.WARNING, _for_error, SafeFormatter(FILE_FORMAT)))
    except OSError as e:
        root.warning("log files unavailable: %s", e)
    for h in _handlers:
        root.addHandler(h)
