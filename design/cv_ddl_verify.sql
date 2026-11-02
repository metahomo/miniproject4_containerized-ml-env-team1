-- cv_ddl_verify.sql — 위반 시도 목록 (각 문장은 거부되어야 한다). 실측: 2026-09-28 SQLite 3.51.0
-- 실행 전 cv_ddl.sql 과 정상 시드가 적재되어 있어야 한다. 아래 각 문장은 개별 트랜잭션으로 실행한다.

-- G8 BR-CV-04 혼잡 상한 >= 여유 하한
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_threshold_order
INSERT INTO threshold_policy VALUES (9,20,50,'2027-01-01T00:00:00','2026-09-28T09:00:00','op1');

-- G8 등급 경계 범위 밖
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_threshold_range
INSERT INTO threshold_policy VALUES (9,120,20,'2027-01-01T00:00:00','2026-09-28T09:00:00','op1');

-- G8 UC8 E4 적용 시작일 과거 (트리거)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: G8: threshold_policy.effective_from must not be in the past
INSERT INTO threshold_policy VALUES (9,50,20,'2026-09-27T00:00:00','2026-09-28T09:00:00','op1');

-- G8 BR-CV-26 시연 모드 켜짐 + 종료 예정 시각 없음
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_demo_end
INSERT INTO validity_policy VALUES (9,'headway',1.0,30,10,1,1,NULL,'2026-09-28T00:00:00',NULL,'2026-09-28T00:00:00','op1');

-- G8 UC11 E1 상한 < 기본값
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_validity_cap
INSERT INTO validity_policy VALUES (9,'headway',1.0,5,10,1,0,NULL,'2026-09-28T00:00:00',NULL,'2026-09-28T00:00:00','op1');

-- G8 예외 노선이 기준 정보에 없음 (FK)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: FOREIGN KEY constraint failed
INSERT INTO validity_route_exception VALUES (1,'R999',5);

-- G8 UC7 E1 정원 0
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_spec_capacity
INSERT INTO vehicle_spec VALUES (9,'VT_LOW',0,0,'x','2026-10-01T00:00:00',NULL,'2026-09-28T09:00:00','op1');

-- G8 UC7 E3 좌석 > 정원
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_spec_seat
INSERT INTO vehicle_spec VALUES (9,'VT_LOW',40,50,'x','2026-10-01T00:00:00',NULL,'2026-09-28T09:00:00','op1');

-- BR-CV-16 제원 출처 없음
-- 기대: 거부 / 실측: REJECTED — IntegrityError: NOT NULL constraint failed: vehicle_spec.source
INSERT INTO vehicle_spec VALUES (9,'VT_LOW',40,30,NULL,'2026-10-01T00:00:00',NULL,'2026-09-28T09:00:00','op1');

-- G8 UC6 E1 다각형 꼭짓점 2개
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_roi_polygon
INSERT INTO roi VALUES (9,'CAM-B12','0,0 1,1',2,10,'2026-10-01T00:00:00',NULL,'2026-09-28T09:00:00','op1');

-- G3 미등록 카메라에 ROI (FK)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: FOREIGN KEY constraint failed
INSERT INTO roi VALUES (9,'CAM-XX','0,0 1,0 1,1',3,10,'2026-10-01T00:00:00',NULL,'2026-09-28T09:00:00','op1');

-- G9 UC12 E2 같은 카메라 두 번째 활성 매핑 (부분 UNIQUE)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: UNIQUE constraint failed: camera_vehicle_map.camera_id
INSERT INTO camera_vehicle_map VALUES (9,'CAM-B12','5678','VT_LOW','verified','2026-09-28T09:00:00','2026-09-28T09:00:00',NULL,'2026-09-28T09:00:00','op1','select');

-- G9 검증됨인데 검증 시각 없음
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_map_verified
INSERT INTO camera_vehicle_map VALUES (9,'CAM-S03','5678',NULL,'verified',NULL,'2026-09-28T09:00:00',NULL,'2026-09-28T09:00:00','op1','csv');

-- BR-CV-03 점유율 범위 밖
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_occupied_range
INSERT INTO assessment (assessment_id,request_id,roi_id,spec_id,threshold_policy_id,model_package_id,occupied_area_ratio,crowding_level,mean_confidence,processed_at) VALUES (9,2,1,1,1,1,130,'free',0.9,'2026-09-28T09:00:00');

-- BR-CV-07 G6 신뢰도 0.5 인데 확정 등급
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_low_confidence_uncertain
INSERT INTO diagnosis_request VALUES (9,'single','web','CAM-B12',NULL,NULL,'2026-09-28T09:50:00','JPEG',1920,1080,1,'2026-09-28T09:50:01',NULL,'accepted',NULL); INSERT INTO assessment (assessment_id,request_id,roi_id,spec_id,threshold_policy_id,model_package_id,occupied_area_ratio,crowding_level,mean_confidence,processed_at) VALUES (9,9,1,1,1,1,40,'free',0.5,'2026-09-28T09:50:02');

-- BR-CV-06 G6 blur 경고를 확정 등급 결과에 부착 (트리거)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: BR-CV-06/07 (G6): quality warning requires crowding_level = uncertain
INSERT INTO assessment_warning VALUES (1,'blur',NULL,'x');

-- 경고 코드 미정의 값을 unknown 없이
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: warning_code IN ('blur','low_light','backligh
INSERT INTO assessment_warning VALUES (2,'fog',NULL,'x');

-- G2 BR-CV-11 반려인데 사유 없음
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_reject_reason
INSERT INTO diagnosis_request VALUES (9,'single','web','CAM-B12',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-09-28T09:50:01',NULL,'rejected',NULL);

-- BR-CV-09 원본 프레임 컬럼 없음 (컬럼 자체가 없어 거부)
-- 기대: 거부 / 실측: REJECTED — OperationalError: table diagnosis_request has no column named frame_blob
INSERT INTO diagnosis_request (request_id,kind,caller_id,camera_id,received_at,status,frame_blob) VALUES (9,'single','web','CAM-B12','2026-09-28T09:50:01','accepted',x'00');

-- BR-CV-26 시연 실측인데 실측 시각 != 등록 시각
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_demo_measured
INSERT INTO camera_measurement VALUES (9,2,1,1,'2026-09-28T09:42:08','2026-09-28T09:42:10',1,12,'2026-09-28T09:54:08',NULL);

-- G10 승강장 카메라 매핑으로 실측 등록 (트리거 — R21-D8 정정으로 복원)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: G10: measurement camera must be in-vehicle type
INSERT INTO camera_vehicle_map VALUES (8,'CAM-S03','7777',NULL,'verified','2026-09-28T09:00:00','2026-09-28T09:00:00',NULL,'2026-09-28T09:00:00','op1','select'); INSERT INTO camera_measurement VALUES (9,2,8,1,'2026-09-28T09:42:08','2026-09-28T09:42:08',0,12,'2026-09-28T09:54:08',NULL);

-- CHECK 장소 유형 — 값 목록 밖 (train_in 추가 후에도 임의 값은 거부)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed
INSERT INTO camera (camera_id,place_type,route_id,stop_id,vehicle_type_id,roi_stale,registered_at,registered_by) VALUES ('CAM-X9','tram_in','R102',NULL,NULL,0,'2026-09-20T09:00:00','op1');

-- BR-CV-23 같은 카메라 두 번째 활성 실측 (부분 UNIQUE)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: UNIQUE constraint failed: camera_measurement.map_id
INSERT INTO camera_measurement VALUES (9,2,1,1,'2026-09-28T09:42:08','2026-09-28T09:42:10',0,12,'2026-09-28T09:54:08',NULL);

-- BR-CV-27 커버리지 분자 > 분모
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_coverage
INSERT INTO vehicle_measurement VALUES (9,'5678',1,'2026-09-28T09:00:00',1,'2026-09-28T09:00:00',50,'normal',3,2,'2026-09-28T09:12:00',0,NULL);

-- BR-CV-19 G0 웜업 전 ready
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_ready_requires_warmup
INSERT INTO server_instance VALUES (9,1,'http://x',8000,NULL,'2026-09-28T08:00:00',NULL,NULL,'ready','2026-09-28T08:00:00');

-- SC-01/02 판정 불일치 (78% 인데 pass)
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_verdict
INSERT INTO batch VALUES (1,'CAM-S03','verification','op1','2026-09-28T09:00:00',10); INSERT INTO verification_run VALUES (1,1,1,1,1,87,78,'pass','2026-09-28T09:30:00',NULL,NULL);

-- G17 BR-CV-30 검증 없이 published
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_guide_published
INSERT INTO api_guide VALUES (9,'v9','published',NULL,NULL,NULL,'2026-09-28T09:00:00','2026-09-28T09:00:00');

-- U5 해제 주체 본인인데 요청 전송 기록
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_gate_request
INSERT INTO gate_event VALUES (9,'G8','S3','policy','1','2026-09-28T09:00:00','PAST_DATE',NULL,'self','2026-09-28T09:00:01','op1',NULL,NULL,NULL);

-- G3 해제 주체 미정 게이트에 해제 기록
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_gate_undefined
INSERT INTO gate_event VALUES (9,'G3','S2','camera','CAM-XX','2026-09-28T09:00:00','CAMERA_MISSING',NULL,'undefined',NULL,NULL,'2026-09-28T09:10:00','op1',NULL);

-- G12 arrival ok 인데 차량 없음
-- 기대: 거부 / 실측: REJECTED — IntegrityError: CHECK constraint failed: chk_arrival_ok
INSERT INTO arrival_snapshot VALUES (9,'R102','S3001',NULL,NULL,NULL,'2026-09-28T09:00:00','ok');
