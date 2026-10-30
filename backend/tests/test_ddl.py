"""T008 — cv_ddl.sql 회귀: 위반 29건 거부(cv_ddl_verify.sql), 뷰 존재, 멱등 재적용."""
import re
import sqlite3

from cv_api import db
from cv_api.settings import REPO_ROOT
import os
import pytest

pytestmark = pytest.mark.skipif(bool(os.environ.get("PG_APP_URL")), reason="SQLite 전용 (PostgreSQL 은 test_ddl_postgres.py)")

VIEWS = ["v_readiness", "v_camera_readiness", "v_vehicle_measurement_status", "v_route_validity_minutes", "v_assessment", "v_audit_record",
         "v_next_vehicle", "v_verification_item", "v_gate_open", "v_current_roi", "v_current_spec", "v_active_mapping", "v_current_threshold", "v_current_validity"]


def test_views_exist_and_idempotent(fresh_db):
    with db.connect() as conn:
        names = {r["name"] for r in db.q(conn, "SELECT name FROM sqlite_master WHERE type='view'")}
        assert set(VIEWS) <= names
    assert db.init_db()["migrations"] == []          # 두 번째 적용은 아무것도 바꾸지 않는다


def test_violations_rejected(fresh_db):
    """cv_ddl_verify.sql 의 각 문장을 시드 위에 실행해 전부 거부되는지 확인 (SD_03 §15-1 재현)."""
    verify = (REPO_ROOT / "design" / "cv_ddl_verify.sql").read_text(encoding="utf-8")
    blocks = [b for b in re.split(r"\n(?=-- )", verify) if "INSERT" in b]
    # 시드는 SD_03 verify.py 와 같은 것을 최소 재현
    seed = """
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
    path = fresh_db.replace("sqlite:///", "")
    con = sqlite3.connect(path); con.isolation_level = None; con.execute("PRAGMA foreign_keys=ON")
    con.executescript(seed)
    rejected = 0
    for b in blocks:
        sql = "\n".join(l for l in b.splitlines() if not l.startswith("--")).strip()
        con.execute("BEGIN")
        try:
            for stmt in [x for x in sql.split(";") if x.strip()]:
                con.execute(stmt)
            con.execute("ROLLBACK")
        except Exception:
            con.execute("ROLLBACK"); rejected += 1
    assert rejected == len(blocks), f"{rejected}/{len(blocks)} 만 거부됨"
