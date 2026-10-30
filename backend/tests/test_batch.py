"""T055 — 일괄 검증 (UC4, P4): 순서, 단건 동일, 한도 422, 부분 반려, 정합성, SC-01·02 판정."""
from tests.helpers import ADMIN, KEY, make_frame

P = lambda x: (x, 260.0, x + 70.0, 620.0, 0.9)  # noqa: E731


def _batch(client, frames, cam="CAM-B12"):
    return client.post("/v1/diagnose/batch", headers=ADMIN, data={"camera_id": cam}, files=[("frames", (f"f{i}.jpg", b, "image/jpeg")) for i, b in enumerate(frames)])


def test_order_and_equal_to_single(client, stub):
    stub.boxes = [P(200), P(400)]
    single = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")}).json()
    r = _batch(client, [make_frame(), make_frame(), make_frame()])
    j = r.json()
    assert r.status_code == 200 and [it["seq"] for it in j["items"]] == [1, 2, 3]
    for it in j["items"]:
        a = it["assessment"]
        assert a["vacant_capacity_ratio"] == single["vacant_capacity_ratio"] and a["crowding_level"] == single["crowding_level"]
        assert a["versions"] == single["versions"]
    assert j["consistency"]["roi_id"] == single["versions"]["roi_id"] and j["consistency"]["audit_records"] == 3


def test_limit_and_partial_reject(client, stub, monkeypatch):
    from cv_api.settings import get_settings
    monkeypatch.setattr(get_settings(), "BATCH_MAX_FRAMES", 3)
    assert _batch(client, [make_frame()] * 4).status_code == 422
    stub.boxes = [P(200)]
    j = _batch(client, [make_frame(), b"BM" + b"\0" * 50, make_frame()]).json()
    assert [it["status"] for it in j["items"]] == ["accepted", "rejected", "accepted"]
    assert j["items"][1]["reject"]["gate"] == "G2"


def test_verification_run_verdict(client, stub):
    stub.boxes = [P(90 + i * 15) for i in range(66)]           # 66 ÷ 80 → 잔여 17.5 crowded
    j = _batch(client, [make_frame(), make_frame(), make_frame(blur=True), b"BM" + b"\0" * 50]).json()
    items = [{"seq": 1, "manual_ratio": 20, "manual_level": "crowded"},
             {"seq": 2, "manual_ratio": 40, "manual_level": "normal"},       # 20%p 차이·등급 불일치
             {"seq": 3, "manual_ratio": 15, "manual_level": "crowded"},      # 판독 불확실 → 제외
             {"seq": 4, "manual_ratio": 15, "manual_level": "crowded"}]      # 반려 → 제외
    r = client.post("/v1/admin/verification-runs", headers=ADMIN, json={"batch_id": j["batch_id"], "items": items})
    v = r.json()
    assert r.status_code == 201 and v["ratio_match_rate"] == 50.0 and v["level_match_rate"] == 50.0 and v["verdict"] == "fail"
    assert [it["excluded"] for it in v["items"]] == [False, False, True, True]
    assert v["versions"]["roi_id"] and v["versions"]["model_commit"]


def test_run_invalidated_on_policy_change(client, stub):
    from cv_api import db
    from datetime import datetime, timedelta, timezone
    stub.boxes = [P(200)]
    j = _batch(client, [make_frame()]).json()
    client.post("/v1/admin/verification-runs", headers=ADMIN, json={"batch_id": j["batch_id"], "items": [{"seq": 1, "manual_ratio": 90, "manual_level": "free"}]})
    fut = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    client.post("/v1/admin/policies/threshold", headers=ADMIN, json={"free_min_ratio": 60, "crowded_max_ratio": 20, "effective_from": fut})
    with db.connect() as conn:
        assert db.q1(conn, "SELECT invalidated_at FROM verification_run")["invalidated_at"] is not None


def test_verification_run_from_manual_persons(client, stub):
    """사람이 센 인원만 넣으면 정원(80)·등급 기준(50/20)으로 잔여 %·등급을 만들어 비교한다 (2026-09-30)."""
    from cv_api import db
    stub.boxes = [P(90 + i * 15) for i in range(66)]           # AI 66명 → 잔여 17.5 crowded
    j = _batch(client, [make_frame(), make_frame()]).json()
    items = [{"seq": 1, "manual_persons": 64},                  # 잔여 20 crowded → ±10%p·등급 일치
             {"seq": 2, "manual_persons": 40}]                  # 잔여 50 free → 둘 다 불일치
    r = client.post("/v1/admin/verification-runs", headers=ADMIN, json={"batch_id": j["batch_id"], "items": items})
    v = r.json()
    assert r.status_code == 201 and v["ratio_match_rate"] == 50.0 and v["level_match_rate"] == 50.0
    one, two = v["items"]
    assert one["manual_ratio"] == 20.0 and one["manual_level"] == "crowded" and one["persons_diff"] == 2 and one["capacity"] == 80
    assert two["manual_ratio"] == 50.0 and two["manual_level"] == "free" and two["persons_diff"] == 26
    with db.connect() as conn:                                  # 저장은 만든 잔여 %·등급 (스키마 변경 없음)
        assert [r["manual_level"] for r in db.q(conn, "SELECT manual_level FROM verification_item ORDER BY request_id")] == ["crowded", "free"]
