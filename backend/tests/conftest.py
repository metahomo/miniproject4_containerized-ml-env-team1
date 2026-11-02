"""테스트 픽스처 — 임시 SQLite + DDL + 시드, 스텁 검출기 주입, 합성 프레임 생성기 (T031)."""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

os.environ.setdefault("DETECTOR", "stub")
os.environ.setdefault("EXTERNAL_PROVIDER", "fixture")
os.environ.setdefault("API_KEYS", "web:changeme-web")        # 테스트는 운영 .env 의 키와 무관하게 고정 키 (T095 키 교체)
os.environ.setdefault("ADMIN_KEYS", "op1:changeme-admin")
os.environ.setdefault("COUNT_CONF_MIN", "0.4")                # 테스트는 운영 .env 의 인원 세기 기준(머리 모델 0.2)과 무관하게 기본값

from cv_api import db  # noqa: E402
from cv_api.settings import get_settings  # noqa: E402

from tests.helpers import ADMIN, KEY, make_frame  # noqa: E402,F401


PG_APP_URL = os.environ.get("PG_APP_URL")   # 있으면 앱 테스트 전체를 PostgreSQL 로 (T073 후속). 테스트마다 public 스키마를 비운다 — 전용 DB 에만


@pytest.fixture()
def fresh_db(tmp_path: Path, monkeypatch):
    url = PG_APP_URL or f"sqlite:///{tmp_path / 'test.db'}"
    if PG_APP_URL:
        from sqlalchemy import create_engine, text
        eng = create_engine(PG_APP_URL)
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE")); c.execute(text("CREATE SCHEMA public"))
        eng.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    db.reset_engine(url)
    db.init_db()
    yield url
    get_settings.cache_clear()


@pytest.fixture()
def seeded(fresh_db):
    """노선 R102, 정류장 3001, 유형 VT_LOW(정원 80), 카메라 CAM-B12(차내, ROI 6.5㎡)·CAM-S03(승강장, ROI 없음), 등급 50/20, 유효 시간 규칙."""
    from cv_api.tools.load_reference import load
    from cv_api.settings import BACKEND_DIR

    load(BACKEND_DIR / "data" / "routes.csv", BACKEND_DIR / "data" / "stops.csv")
    now = db.now_iso()
    with db.connect() as conn:
        db.insert(conn, "vehicle_type", {"vehicle_type_id": "VT_LOW", "type_name": "저상버스"})
        db.insert(conn, "camera", {"camera_id": "CAM-B12", "place_type": "bus_in", "route_id": "R102", "stop_id": None, "vehicle_type_id": "VT_LOW",
                                   "roi_stale": 0, "registered_at": now, "registered_by": "t", "powered": 1})
        db.insert(conn, "camera", {"camera_id": "CAM-B13", "place_type": "bus_in", "route_id": "R102", "stop_id": None, "vehicle_type_id": "VT_LOW",
                                   "roi_stale": 0, "registered_at": now, "registered_by": "t", "powered": 1})
        db.insert(conn, "camera", {"camera_id": "CAM-S03", "place_type": "platform", "route_id": "R102", "stop_id": "3001", "vehicle_type_id": None,
                                   "roi_stale": 0, "registered_at": now, "registered_by": "t", "powered": 1})
        for cam in ("CAM-B12", "CAM-B13"):
            db.insert(conn, "roi", {"camera_id": cam, "polygon": "80,300 1200,300 1200,680 80,680", "vertex_count": 4, "area": 425600.0,
                                    "roi_area_m2": 6.5, "footprint_m2": None, "effective_from": "2026-01-01T00:00:00", "superseded_at": None,
                                    "created_at": now, "created_by": "t"})
        db.insert(conn, "vehicle_spec", {"vehicle_type_id": "VT_LOW", "capacity": 80, "seat_count": 30, "source": "제원표",
                                         "effective_from": "2026-01-01T00:00:00", "superseded_at": None, "created_at": now, "created_by": "t"})
        db.insert(conn, "threshold_policy", {"free_min_ratio": 50, "crowded_max_ratio": 20, "effective_from": "2026-01-01T00:00:00", "created_at": "2025-12-31T00:00:00", "created_by": "t"})
        pid = db.insert(conn, "validity_policy", {"basis": "headway", "factor": 1.0, "cap_minutes": 30, "default_minutes": 10, "window_minutes": 1,
                                                  "demo_on": 0, "demo_end_at": None, "effective_from": "2026-01-01T00:00:00", "superseded_at": None,
                                                  "created_at": now, "created_by": "t"})
        db.insert(conn, "validity_route_exception", {"policy_id": pid, "route_id": "R102", "minutes": 12})
    return fresh_db


@pytest.fixture()
def stub(seeded):
    """StubDetector 를 런타임에 주입하고 startup 을 돌려 ready 로 만든다. boxes 를 바꿔 시나리오를 만든다."""
    from cv_api.predict import StubDetector
    from cv_api.services import ops

    det = StubDetector(boxes=[])
    ops.runtime.set_detector(det)
    ops.runtime.instance_id = None
    ops.startup(get_settings())
    return det


@pytest.fixture()
def client(stub):
    from fastapi.testclient import TestClient
    from cv_api.app import create_app

    app = create_app()
    app.router.lifespan_context = _noop_lifespan  # startup 은 stub 픽스처가 이미 수행
    with TestClient(app) as c:
        yield c


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(app):
    yield
