"""T073 — PostgreSQL 이식본(cv_ddl.postgres.sql) 실행 검증. PG_TEST_URL 이 있을 때만 돈다.

    PG_TEST_URL='postgresql+psycopg://postgres:@/postgres?host=<소켓 디렉터리>' pytest tests/test_ddl_postgres.py

검증: ① 무오류 적용 ② 재적용 멱등(마이그레이션 없음) ③ 뷰 14개 ④ cv_ddl_verify.sql 위반 시도 전부 거부(30건)(부분 UNIQUE·트리거·CHECK·FK).
테스트마다 public 스키마를 비우고 시작한다 — 전용 검증 DB 에만 쓴다.
"""
import os
import re

import pytest
from sqlalchemy import create_engine, text

from cv_api import db
from cv_api.settings import REPO_ROOT, get_settings
from tests.test_ddl import VIEWS

PG = os.environ.get("PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG, reason="PG_TEST_URL 없음 — PostgreSQL 검증 생략")

SEED = """
INSERT INTO route VALUES ('R102','bus','102번','TAGO');
INSERT INTO stop VALUES ('S3001','R102','충남대','bus_stop');
INSERT INTO vehicle_type VALUES ('VT_LOW','저상버스');
INSERT INTO camera (camera_id,place_type,route_id,stop_id,vehicle_type_id,roi_stale,registered_at,registered_by) VALUES ('CAM-B12','bus_in','R102',NULL,'VT_LOW',0,'2026-09-20T09:00:00','op1');
INSERT INTO camera (camera_id,place_type,route_id,stop_id,vehicle_type_id,roi_stale,registered_at,registered_by) VALUES ('CAM-S03','platform','R102','S3001',NULL,0,'2026-09-20T09:00:00','op1');
INSERT INTO roi (roi_id,camera_id,polygon,vertex_count,area,effective_from,superseded_at,created_at,created_by) VALUES (1,'CAM-B12','0,0 1,0 1,1',4,95000,'2026-09-20T00:00:00',NULL,'2026-09-20T09:00:00','op1');
INSERT INTO vehicle_spec (spec_id,vehicle_type_id,capacity,seat_count,source,effective_from,superseded_at,created_at,created_by) VALUES (1,'VT_LOW',80,30,'x','2026-09-20T00:00:00',NULL,'2026-09-20T09:00:00','op1');
INSERT INTO camera_vehicle_map (map_id,camera_id,vehicle_id,vehicle_type_id,verify_status,verified_at,effective_from,released_at,created_at,created_by,input_method) VALUES (1,'CAM-B12','1234','VT_LOW','verified','2026-09-21T09:00:00','2026-09-21T09:00:00',NULL,'2026-09-21T09:00:00','op1','select');
INSERT INTO threshold_policy (policy_id,free_min_ratio,crowded_max_ratio,effective_from,created_at,created_by) VALUES (1,50,20,'2026-09-01T00:00:00','2026-08-30T09:00:00','op1');
INSERT INTO validity_policy (policy_id,basis,factor,cap_minutes,default_minutes,window_minutes,demo_on,demo_end_at,effective_from,superseded_at,created_at,created_by) VALUES (1,'headway',1.0,30,10,1,0,NULL,'2026-09-01T00:00:00',NULL,'2026-09-01T00:00:00','op1');
INSERT INTO model_package (model_package_id,repo_url,commit_hash,weights_file,license,required_versions,contract_check_result,fetched_at,fetched_by) VALUES (1,'r','a1','w',NULL,NULL,'ok','2026-09-27T10:00:00','op1');
INSERT INTO diagnosis_request (request_id,kind,caller_id,camera_id,batch_id,batch_seq,captured_at,image_format,width,height,size_bytes,received_at,responded_at,status,reject_reason) VALUES (1,'measurement','web','CAM-B12',NULL,NULL,'2026-09-28T09:38:20','JPEG',1920,1080,1,'2026-09-28T09:38:21','2026-09-28T09:38:22','accepted',NULL);
INSERT INTO assessment (assessment_id,request_id,roi_id,spec_id,threshold_policy_id,model_package_id,occupied_area_ratio,crowding_level,mean_confidence,processed_at) VALUES (1,1,1,1,1,1,85,'crowded',0.77,'2026-09-28T09:38:22');
INSERT INTO diagnosis_request (request_id,kind,caller_id,camera_id,batch_id,batch_seq,captured_at,image_format,width,height,size_bytes,received_at,responded_at,status,reject_reason) VALUES (2,'single','web','CAM-B12',NULL,NULL,NULL,'JPEG',1,1,1,'2026-09-28T09:42:09','2026-09-28T09:42:10','accepted',NULL);
INSERT INTO assessment (assessment_id,request_id,roi_id,spec_id,threshold_policy_id,model_package_id,occupied_area_ratio,crowding_level,mean_confidence,processed_at) VALUES (2,2,1,1,1,1,59,'uncertain',0.52,'2026-09-28T09:42:10');
INSERT INTO camera_measurement (cm_id,assessment_id,map_id,validity_policy_id,measured_at,registered_at,is_demo,validity_minutes,expires_at,superseded_at) VALUES (1,1,1,1,'2026-09-28T09:38:20','2026-09-28T09:38:22',0,12,'2026-09-28T09:50:20',NULL);
"""


@pytest.fixture()
def pg(monkeypatch):
    with create_engine(PG).begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE")); c.execute(text("CREATE SCHEMA public"))
    monkeypatch.setenv("DATABASE_URL", PG)
    get_settings.cache_clear()
    db.reset_engine(PG)
    yield PG
    get_settings.cache_clear()


def test_apply_idempotent_and_views(pg):
    first = db.init_db()
    assert first["statements"] > 50
    assert db.init_db()["migrations"] == []                     # 재적용: 추가 컬럼 6개가 이미 정본에 있다
    with db.connect() as conn:
        views = {r["table_name"] for r in db.q(conn, "SELECT table_name FROM information_schema.views WHERE table_schema='public'")}
        cols = {r["column_name"] for r in db.q(conn, "SELECT column_name FROM information_schema.columns WHERE table_name='server_instance'")}
        trig = {r["trigger_name"] for r in db.q(conn, "SELECT DISTINCT trigger_name FROM information_schema.triggers")}
    assert set(VIEWS) <= views
    assert {"detector_kind", "load_seconds"} <= cols
    assert "trg_cm_in_vehicle_camera" in trig                    # 차내(bus_in·train_in)만 실측 — R21-D8 정정


def test_violations_rejected(pg):
    db.init_db()
    verify = (REPO_ROOT / "design" / "cv_ddl_verify.sql").read_text(encoding="utf-8")
    blocks = [b for b in re.split(r"\n(?=-- )", verify) if "INSERT" in b]
    raw = db.get_engine().raw_connection()
    try:
        cur = raw.cursor()
        for stmt in [x for x in SEED.split(";") if x.strip()]:
            cur.execute(stmt)
        raw.commit()
        passed = []
        for b in blocks:
            sql = "\n".join(l for l in b.splitlines() if not l.startswith("--")).strip()
            try:
                for stmt in [x for x in sql.split(";") if x.strip()]:
                    cur.execute(stmt)
                passed.append(b.splitlines()[0])
            except Exception:  # noqa: BLE001 — 거부가 기대값
                pass
            raw.rollback()
    finally:
        raw.close()
    assert not passed, f"거부되지 않은 {len(passed)}/{len(blocks)}건: {passed}"
