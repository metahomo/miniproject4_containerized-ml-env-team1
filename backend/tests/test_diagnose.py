"""T025 — 진단 게이트·결과: G0 503, G3 404, G4 409(+gate_event), G7 산출 불가, G6 판독 불확실, 인원÷정원 계산(R22), 재현성, 원본 미보관."""
from cv_api import db
from cv_api.services import ops
from tests.helpers import ADMIN, KEY, make_frame

PERSON = lambda x, c=0.9: (x, 260.0, x + 70.0, 620.0, c)   # 발 위치 y=620 → ROI(300~680) 안  # noqa: E731
CROWD = lambda n: [PERSON(90 + i * (1040 // n)) for i in range(n)]   # ROI 안에 n 명  # noqa: E731


def _diag(client, cam="CAM-B12", **kw):
    return client.post("/v1/diagnose", headers=KEY, data={"camera_id": cam, **kw}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})


def test_g0_not_ready_503(client):
    with db.connect() as conn:
        db.update(conn, "server_instance", "instance_id=:i", {"readiness": "preparing"}, i=ops.runtime.instance_id)
    r = _diag(client)
    assert r.status_code == 503 and r.json()["gate"] == "G0" and r.json()["resolver_role"] == "operator"


def test_g1_missing_key(client):
    r = client.post("/v1/diagnose", data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    assert r.status_code == 401


def test_g3_unknown_camera_404(client):
    r = _diag(client, cam="CAM-XX")
    assert r.status_code == 404 and r.json()["gate"] == "G3"


def test_g4_roi_missing_409_with_event(client):
    r = _diag(client, cam="CAM-S03")
    j = r.json()
    assert r.status_code == 409 and j["gate"] == "G4" and j["gate_event_id"]
    # C7 요청 보내기
    r2 = client.post(f"/v1/gate-events/{j['gate_event_id']}/request", headers=KEY)
    assert r2.status_code == 200 and r2.json()["request_sent_at"]


def test_normal_free_and_person_count_math(client, stub):
    stub.boxes = [PERSON(200), PERSON(400), PERSON(600), (900, 0, 950, 280, 0.9),   # 발 위치 y=280 → ROI 밖 (FR-03)
                  PERSON(800, 0.3)]                                                  # 인원 세기 기준(0.4) 미만 → 세지 않음
    r = _diag(client, captured_at="2026-09-28T09:41:00")
    assert r.status_code == 200
    j = r.json()
    assert j["person_count"] == 3 and j["capacity"] == 80 and j["over_capacity"] is False
    # R22: 3명 ÷ 정원 80 = 3.75% 점유 → 잔여 96.25 → free. 0.3 박스는 평균 신뢰도에도 들지 않는다
    assert j["occupied_area_ratio"] == 3.75 and j["crowding_level"] == "free" and j["is_reference_only"] is False
    assert j["mean_confidence"] == 0.9 and j["remaining_persons"] == 77
    assert j["notice"] and j["versions"]["roi_id"] and j["versions"]["threshold_policy_id"]
    assert j["warnings"] == []


def test_crowded_mapping(client, stub):
    stub.boxes = CROWD(66)                                       # 66 ÷ 80 = 82.5% 점유 → 잔여 17.5% → crowded
    j = _diag(client).json()
    assert j["person_count"] == 66 and j["crowding_level"] == "crowded" and j["vacant_capacity_ratio"] == 17.5 and j["remaining_persons"] == 14


def test_over_capacity_stops_at_100(client, stub):
    stub.boxes = CROWD(90)                                       # 90 명 > 정원 80 → 점유 100% 에서 멈춤, 정원 초과 표시
    j = _diag(client).json()
    assert j["person_count"] == 90 and j["occupied_area_ratio"] == 100 and j["vacant_capacity_ratio"] == 0
    assert j["over_capacity"] is True and j["remaining_persons"] == 0 and j["crowding_level"] == "crowded"


def test_count_conf_min_from_policy(client, stub):
    """R22: 인원 세기 기준은 등급 기준 판본에 딸린 값 — 운영 관리자가 S3 에서 바꾼다."""
    stub.boxes = [PERSON(200), PERSON(400, 0.3)]
    assert _diag(client).json()["person_count"] == 1
    with db.connect() as conn:
        db.insert(conn, "threshold_policy", {"free_min_ratio": 50, "crowded_max_ratio": 20, "count_conf_min": 0.25,
                                             "effective_from": "2026-02-01T00:00:00", "created_at": "2026-01-15T00:00:00", "created_by": "t"})
    assert _diag(client).json()["person_count"] == 2


def test_g6_low_confidence_uncertain(client, stub):
    stub.boxes = [(200, 260, 270, 620, 0.5), (400, 260, 470, 620, 0.5)]
    j = _diag(client).json()
    assert j["crowding_level"] == "uncertain" and j["is_reference_only"] is True
    assert "low_confidence" in [w["code"] for w in j["warnings"]]


def test_g6_blur_uncertain(client, stub):
    stub.boxes = [PERSON(200)]
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(blur=True), "image/jpeg")})
    j = r.json()
    assert j["crowding_level"] == "uncertain" and "blur" in [w["code"] for w in j["warnings"]]


def test_g7_no_capacity(client, stub):
    with db.connect() as conn:
        db.update(conn, "camera", "camera_id=:c", {"vehicle_type_id": None}, c="CAM-B12")
    stub.boxes = [PERSON(200), PERSON(400)]
    j = _diag(client).json()
    # R22: 정원이 없으면 인원만 산출, 혼잡도는 산출 불가(판독 불확실 + unknown 경고)
    assert j["remaining_not_computable"] is True and j["remaining_persons"] is None and j["capacity"] is None
    assert j["person_count"] == 2 and j["crowding_level"] == "uncertain"
    assert any(w["code"] == "unknown" and "정원 미등록" in (w["detail"] or "") for w in j["warnings"])


def test_reproducible_same_input_same_output(client, stub):
    stub.boxes = [PERSON(200), PERSON(400)]
    a, b = _diag(client).json(), _diag(client).json()
    for k in ("occupied_area_ratio", "vacant_capacity_ratio", "crowding_level", "person_count", "remaining_persons"):
        assert a[k] == b[k]


def test_no_image_stored(client, stub):
    _diag(client)
    with db.connect() as conn:
        cols = set(db._columns(conn, "diagnosis_request"))   # 방언 중립 (SQLite·PostgreSQL)
        row = db.q1(conn, "SELECT * FROM v_audit_record ORDER BY at DESC LIMIT 1")
    assert not any(c in ("frame", "image", "blob", "frame_data", "image_data") for c in cols)
    assert row and row["camera_id"] == "CAM-B12" and "caller_id" not in row


def test_roi_stale_warning(client, stub):
    with db.connect() as conn:
        db.update(conn, "camera", "camera_id=:c", {"roi_stale": 1}, c="CAM-B12")
    j = _diag(client).json()
    assert "roi_stale" in [w["code"] for w in j["warnings"]]
