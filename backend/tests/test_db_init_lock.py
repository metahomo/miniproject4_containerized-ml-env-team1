"""처음 기동할 때 WAL 전환이 겹쳐 DB 초기화가 실패하던 문제 — 재시도, 스케줄러 대기, 실패 로그 (2026-11-02)."""
import asyncio
import logging
import os
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from cv_api import db
from cv_api.app import create_app
from cv_api.services import camera_power, ops
from cv_api.settings import get_settings

sqlite_only = pytest.mark.skipif(bool(os.environ.get("PG_APP_URL")), reason="SQLite 전용")


class FakeCursor:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def execute(self, _sql):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)


def test_wal_retries_when_locked(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda _s: None)
    cur = FakeCursor([sqlite3.OperationalError("database is locked")] * 3)
    db._enable_wal(cur)
    assert cur.calls == 4


def test_wal_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda _s: None)
    cur = FakeCursor([sqlite3.OperationalError("database is locked")] * db.WAL_RETRIES)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        db._enable_wal(cur)
    assert cur.calls == db.WAL_RETRIES


def test_wal_does_not_retry_other_errors(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda _s: pytest.fail("다시 시도하면 안 된다"))
    cur = FakeCursor([sqlite3.OperationalError("disk I/O error")])
    with pytest.raises(sqlite3.OperationalError, match="disk"):
        db._enable_wal(cur)
    assert cur.calls == 1


@sqlite_only
@pytest.mark.parametrize("round_", range(5))
def test_concurrent_first_connections_create_schema(tmp_path, monkeypatch, round_):
    """새 파일에 여러 스레드가 동시에 처음 연결해도 초기화가 성공한다."""
    url = f"sqlite:///{tmp_path / f'race{round_}.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        engines = [db._make_engine(url) for _ in range(6)]
        barrier = threading.Barrier(len(engines))
        errors = []

        def first_connect(eng):
            barrier.wait()
            try:
                eng.connect().close()
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=first_connect, args=(e,)) for e in engines]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        db.reset_engine(url)
        assert db.init_db()["statements"] > 0
    finally:
        for e in engines:
            e.dispose()
        get_settings.cache_clear()


def test_scheduler_waits_for_startup(monkeypatch):
    """스케줄러는 startup 이 끝나기(instance_id 가 생기기) 전에 DB 를 건드리지 않는다."""
    calls = []
    monkeypatch.setattr(camera_power, "due_cameras", lambda: calls.append(1) or [])
    monkeypatch.setattr(ops.runtime, "instance_id", None)

    async def scenario():
        task = asyncio.create_task(camera_power.scheduler_loop(get_settings(), tick_s=0.01))
        await asyncio.sleep(0.05)
        before = len(calls)
        ops.runtime.instance_id = 1
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return before

    assert asyncio.run(scenario()) == 0
    assert calls


@pytest.mark.parametrize("role,target", [("all", "startup"), ("web", "init_db")])
def test_startup_failure_is_logged(fresh_db, monkeypatch, caplog, role, target):
    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ops, target, boom) if target == "startup" else monkeypatch.setattr(db, target, boom)
    monkeypatch.setattr(ops.runtime, "instance_id", None)
    with caplog.at_level(logging.ERROR, logger="cv_api"):
        with TestClient(create_app(role)):
            pass
    assert "startup failed" in caplog.text and "database is locked" in caplog.text
