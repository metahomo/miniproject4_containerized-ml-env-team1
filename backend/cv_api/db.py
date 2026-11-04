"""DB 접근 계층 — SQLAlchemy Core. 스키마 정본은 design/cv_ddl.sql (SD_03, SQLite 3종 검증 완료).

- apply_ddl(): DDL 파일을 문장 단위로 멱등 실행한다. 트리거 본문의 ';' 를 고려해 BEGIN…END 블록은 한 문장으로 묶는다.
- apply_migrations(): 계획 단계 결정(R20 발 위치 방식)으로 추가된 컬럼을 ADD COLUMN 한다. 정본 갱신은 T074.
- SQLite 는 연결마다 PRAGMA foreign_keys=ON.
"""
from __future__ import annotations

import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine

from .settings import Settings, get_settings

_engine: Optional[Engine] = None
WAL_RETRIES = 50          # busy_timeout 과 같은 5초까지 (0.1초 간격)
WAL_RETRY_SECONDS = 0.1

# 구현 단계 추가 컬럼 — 정본 cv_ddl.sql 에도 반영됨(2026-09-29). 그 전에 만든 DB 를 위한 ADD COLUMN (테이블, 컬럼, 타입)
MIGRATIONS = [
    ("roi", "roi_area_m2", "REAL"),
    ("roi", "footprint_m2", "REAL"),
    ("assessment", "person_count", "INTEGER"),
    ("model_package", "detector_kind", "VARCHAR(16)"),
    ("server_instance", "detector_kind", "VARCHAR(16)"),
    ("server_instance", "load_seconds", "REAL"),
    ("threshold_policy", "count_conf_min", "REAL"),        # R22 인원 세기 기준
    ("vehicle_measurement", "persons_sum", "INTEGER"),     # R22 합산 인원
    ("vehicle_measurement", "capacity", "INTEGER"),        # R22 합산 당시 정원
    # 카메라 전원 관리 (S2b, 2026-09-29): 기존 카메라도 off 로 시작한다 — 관리자가 켜야 진단한다
    ("camera", "car_position", "INTEGER"),
    ("camera", "powered", "INTEGER NOT NULL DEFAULT 0"),
    ("camera", "powered_at", "VARCHAR(19)"),
    ("camera", "frame_source", "VARCHAR(500)"),
    ("camera", "poll_interval_s", "REAL NOT NULL DEFAULT 10"),
    # API 키 승인 (T108, 2026-09-29): 그 전에 발급된 키는 운영 관리자 본인 발급이었으므로 승인된 것(active)으로 본다.
    #   새 DB 는 DDL 기본값 'pending' — 앱은 늘 status 를 넣는다
    ("api_key", "status", "VARCHAR(10) NOT NULL DEFAULT 'active'"),
    ("api_key", "approved_at", "VARCHAR(19)"),
    ("api_key", "approved_by", "VARCHAR(40)"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def iso(v: Any) -> Any:
    """시각 값을 ISO 문자열('YYYY-MM-DDTHH:MM:SS', UTC)로. None·문자열은 그대로."""
    return v.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(v, datetime) else v


def get_engine(settings: Optional[Settings] = None) -> Engine:
    global _engine
    if _engine is None:
        s = settings or get_settings()
        _engine = _make_engine(s.DATABASE_URL)
    return _engine


def _enable_wal(cur) -> None:  # noqa: ANN001
    """새 DB 를 WAL 로 바꾸는 순간에 다른 연결이 겹치면 busy_timeout 을 기다리지 않고 바로 locked 가 난다 — 짧게 다시 시도한다."""
    for attempt in range(WAL_RETRIES):
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or attempt == WAL_RETRIES - 1:
                raise
            time.sleep(WAL_RETRY_SECONDS)


def _make_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        raise ValueError("DATABASE_URL 은 SQLite 만 지원한다")
    eng = create_engine(url, future=True, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        # 진단 API(9544)와 웹 백엔드(9524) 두 프로세스가 같은 파일을 쓴다 — WAL 로 읽기·쓰기 동시성, 잠금은 5초까지 대기
        cur.execute("PRAGMA busy_timeout=5000")
        if ":memory:" not in url:
            _enable_wal(cur)
        cur.close()

    return eng


def reset_engine(url: Optional[str] = None) -> Engine:
    """테스트용: 엔진을 교체한다."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = _make_engine(url or get_settings().DATABASE_URL)
    return _engine


@contextmanager
def connect() -> Iterator[Connection]:
    with get_engine().begin() as conn:
        yield conn


def split_sql(script: str) -> List[str]:
    """';' 로 나누되 CREATE TRIGGER … BEGIN … END; 는 한 덩어리로 유지한다. 주석 제거."""
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        # 행 끝 주석 제거 — 작은따옴표 짝이 맞는(문자열 밖) 첫 '--' 부터
        idx = line.find("--")
        while idx >= 0 and line[:idx].count("'") % 2 == 1:
            idx = line.find("--", idx + 2)
        if idx >= 0:
            line = line[:idx]
        lines.append(line)
    body = "\n".join(lines)
    stmts, buf, in_trigger = [], [], False
    for part in body.split(";"):
        buf.append(part)
        chunk = ";".join(buf)
        up = chunk.upper()
        if "CREATE TRIGGER" in up and re.search(r"\bBEGIN\b", up) and not in_trigger:
            in_trigger = True
        if in_trigger:
            if re.search(r"\bEND\s*$", chunk.strip(), re.I):
                stmts.append(chunk.strip()); buf, in_trigger = [], False
            continue
        if chunk.strip():
            stmts.append(chunk.strip())
        buf = []
    return [s for s in stmts if s]


def apply_ddl(conn: Connection, ddl_path=None) -> int:
    path = ddl_path or get_settings().DDL_PATH
    script = open(path, encoding="utf-8").read()
    n = 0
    for stmt in split_sql(script):
        if stmt.upper().startswith("PRAGMA"):
            continue  # 연결 이벤트에서 처리
        conn.exec_driver_sql(stmt)
        n += 1
    return n


def _columns(conn: Connection, table: str) -> List[str]:
    return [r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]


_PLACE_TYPES_OLD = "IN ('platform','bus_in')"
_PLACE_TYPES_NEW = "IN ('platform','bus_in','train_in')"


def _widen_place_type(conn: Connection) -> bool:
    """R21-D8 정정(2026-09-29): camera.place_type CHECK 에 'train_in' 을 더한다 — 그 전에 만든 DB 용. 멱등.
    SQLite 는 CHECK 를 ALTER 로 못 바꾼다. 제약을 넓히기만 하므로(기존 행은 모두 만족) SQLite 문서의 writable_schema 방식으로
    스키마 문장만 고치고 schema_version 을 올린다."""
    row = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='camera'").fetchone()
    if not row or _PLACE_TYPES_OLD not in row[0]:
        return False
    ver = conn.exec_driver_sql("PRAGMA schema_version").scalar()
    conn.exec_driver_sql("PRAGMA writable_schema=ON")
    conn.exec_driver_sql("UPDATE sqlite_master SET sql=replace(sql, ?, ?) WHERE type='table' AND name='camera'",
                         (_PLACE_TYPES_OLD, _PLACE_TYPES_NEW))
    conn.exec_driver_sql(f"PRAGMA schema_version={int(ver) + 1}")
    conn.exec_driver_sql("PRAGMA writable_schema=OFF")
    return True


_ROLES_OLD = "IN ('admin','controller','developer')"
_ROLES_NEW = "IN ('admin','controller','user')"


def _account_role_user(conn: Connection) -> bool:
    """T108(2026-09-29): account.role 의 'developer'(연계 개발자) → 'user'(일반 사용자). 그 전에 만든 DB 용. 멱등.
    _widen_place_type 과 같은 방식으로 CHECK 문장을 고친 뒤 행을 바꾼다."""
    row = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='account'").fetchone()
    if not row or _ROLES_OLD not in row[0]:
        return False
    ver = conn.exec_driver_sql("PRAGMA schema_version").scalar()
    conn.exec_driver_sql("PRAGMA writable_schema=ON")
    conn.exec_driver_sql("UPDATE sqlite_master SET sql=replace(sql, ?, ?) WHERE type='table' AND name='account'", (_ROLES_OLD, _ROLES_NEW))
    conn.exec_driver_sql(f"PRAGMA schema_version={int(ver) + 1}")
    conn.exec_driver_sql("PRAGMA writable_schema=OFF")
    conn.exec_driver_sql("UPDATE account SET role='user' WHERE role='developer'")
    return True


# 권한 매트릭스(S10) 표 role_permission 은 정본 DDL(cv_ddl.sql 영역 H)에 있다 — apply_ddl 이 먼저 만든다.
# 예전에는 여기서도 CREATE 했다(정본 반영 전). 2026-09-30 중복 제거.


def apply_migrations(conn: Connection) -> List[str]:
    applied = []
    if _widen_place_type(conn):
        applied.append("camera.place_type+train_in")
    if _account_role_user(conn):
        applied.append("account.role developer→user")
    for table, col, typ in MIGRATIONS:
        if col not in _columns(conn, table):
            try:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            except Exception as e:  # noqa: BLE001 — 다른 프로세스가 먼저 추가한 경우(두 서버 동시 기동)
                if "duplicate column" not in str(e).lower():
                    raise
                continue
            applied.append(f"{table}.{col}")
    return applied


def init_db() -> Dict[str, Any]:
    with connect() as conn:
        n = apply_ddl(conn)
        mig = apply_migrations(conn)
    return {"statements": n, "migrations": mig}


# ---- 얇은 헬퍼 ----
def _row(r) -> Dict[str, Any]:
    # 읽기 경계: 시각은 앱 전체에서 ISO 문자열이다
    return {k: iso(v) for k, v in r._mapping.items()}


def q(conn: Connection, sql: str, **params) -> List[Dict[str, Any]]:
    return [_row(r) for r in conn.execute(text(sql), params).fetchall()]


def q1(conn: Connection, sql: str, **params) -> Optional[Dict[str, Any]]:
    r = conn.execute(text(sql), params).fetchone()
    return _row(r) if r else None


def insert(conn: Connection, table: str, row: Dict[str, Any]) -> int:
    cols = ", ".join(row.keys())
    vals = ", ".join(f":{k}" for k in row.keys())
    pk = conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), row).lastrowid
    return int(pk) if pk is not None else 0


def update(conn: Connection, table: str, where: str, set_: Dict[str, Any], **params) -> int:
    assigns = ", ".join(f"{k} = :set_{k}" for k in set_.keys())
    p = {f"set_{k}": v for k, v in set_.items()}
    p.update(params)
    return conn.execute(text(f"UPDATE {table} SET {assigns} WHERE {where}"), p).rowcount


def executemany(conn: Connection, sql: str, rows: Iterable[Dict[str, Any]]) -> None:
    conn.execute(text(sql), list(rows))
