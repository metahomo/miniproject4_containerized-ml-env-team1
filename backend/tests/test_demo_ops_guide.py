"""T050 시연 · T059 계약 대조(G17) · T065 상시 운영."""
from datetime import datetime, timedelta, timezone

from cv_api import db
from cv_api.services import ops
from tests.helpers import ADMIN, KEY, make_frame

P = lambda x: (x, 260.0, x + 70.0, 620.0, 0.9)  # noqa: E731


def _batch_items(n=2):
    files = [("frame", (f"p{i}.jpg", make_frame(), "image/jpeg")) for i in range(1, n + 1)]
    data = {"seq": [str(i) for i in range(1, n + 1)],
            "vehicle_id": ["1234" if i == 1 else "5678" for i in range(1, n + 1)],
            "camera_id": ["CAM-B12" if i == 1 else "CAM-B13" for i in range(1, n + 1)]}
    return data, files


def test_demo_batch_off_then_on(client, stub):
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B12", "vehicle_id": "1234"})
    client.post("/v1/admin/mappings", headers=ADMIN, json={"camera_id": "CAM-B13", "vehicle_id": "5678"})
    stub.boxes = [P(200)]
    data, files = _batch_items()
    r = client.post("/v1/measurements/batch", headers=ADMIN, data=data, files=files)
    j = r.json()
    assert r.status_code == 200, j
    assert j["demo_mode"] is False and all(it["status"] == "accepted" for it in j["items"])
    client.post("/v1/admin/policies/validity", headers=ADMIN, json={"factor": 1.0, "cap_minutes": 30, "demo_on": True})
    data, files = _batch_items()
    j = client.post("/v1/measurements/batch", headers=ADMIN, data=data, files=files).json()
    assert j["demo_mode"] is True and j["items"][0]["result"]["measurement"]["demo_mode"] is True
    nv = client.get("/v1/next-vehicle", headers=KEY, params={"route_id": "R102", "stop_id": "3001", "limit": 4}).json()
    assert nv["demo_mode"] is True and {v["vehicle_id"]: v["basis_type"] for v in nv["vehicles"]}["1234"] == "measured"


def test_demo_auto_release(client):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")
    client.post("/v1/admin/policies/validity", headers=ADMIN, json={"factor": 1.0, "cap_minutes": 30, "demo_on": True, "demo_end_at": past})
    out = ops.tick()
    assert out.get("demo_auto_released") is True
    assert client.get("/v1/admin/ops-status", headers=ADMIN).json()["demo_on"] is False


def test_readiness_watch_and_g0(client, stub):
    stub._loaded = False
    ops.tick()
    r = client.get("/v1/readiness").json()
    assert r["readiness"] == "unavailable"
    assert client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")}).status_code == 503


def test_retention_disabled_by_default(client, stub):
    stub.boxes = [P(200)]
    client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    ops.tick()
    with db.connect() as conn:
        assert db.q1(conn, "SELECT COUNT(*) AS n FROM assessment")["n"] == 1


def test_guide_contract_g17(client):
    from cv_api.services import guide
    res = guide.verify_and_publish(client.app.openapi())
    assert res["status"] == "published" and res["missing"] == []
    g = client.get("/v1/api-guide").json()
    assert g["catalog"] and g["guideline_md"].startswith("#") and g["model_card_md"] and g["readiness"]["readiness"]
    paths = set(client.app.openapi()["paths"])
    for row in g["catalog"]:
        for p in [x.strip() for x in row["path"].split(",")]:
            assert p in paths
    # 반대 방향도: 실제 엔드포인트는 모두 카탈로그에 있다 (카탈로그가 뒤처지지 않게)
    listed = {x.strip() for row in g["catalog"] for x in row["path"].split(",")}
    assert paths - listed == set(), f"카탈로그에 없는 엔드포인트: {sorted(paths - listed)}"


def test_check_queries_zero(client, stub):
    """SD_03 §13-2 점검 쿼리 Q2·Q3·Q4 가 0건."""
    stub.boxes = [P(200)]
    client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    with db.connect() as conn:
        q2 = db.q(conn, "SELECT a.assessment_id FROM assessment a WHERE a.mean_confidence < 0.6 AND NOT EXISTS (SELECT 1 FROM assessment_warning w WHERE w.assessment_id=a.assessment_id AND w.warning_code='low_confidence')")
        q4 = db.q(conn, "SELECT cm.cm_id FROM camera_measurement cm JOIN camera_vehicle_map m ON m.map_id=cm.map_id WHERE cm.superseded_at IS NULL AND m.released_at IS NOT NULL")
    assert q2 == [] and q4 == []


def test_manual_appendix_lists_every_endpoint(client):
    """매뉴얼 부록 표(방식·주소)가 실제 명세의 엔드포인트와 정확히 같다 — 이용자가 보는 목록이 뒤처지지 않게. 관리자 전용은 B 절에."""
    import re
    manual = client.get("/v1/api-guide", headers=KEY).json()["manual_md"]
    appendix = manual.split("## 부록. 엔드포인트 전체 목록")[1]
    rows = re.findall(r"^\| \d+ \| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)` \|", appendix, re.M)
    actual = {(m.upper(), p) for p, ms in client.app.openapi()["paths"].items() for m in ms}
    assert set(rows) == actual and len(rows) == len(actual), f"부록에 없음 {sorted(actual - set(rows))} / 없어진 것 {sorted(set(rows) - actual)}"
    rows_b = set(re.findall(r"^\| \d+ \| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)` \|", appendix.split("### B.")[1], re.M))
    needs_admin = {(m, p) for m, p in actual if p.startswith("/v1/admin/") or p in ("/v1/diagnose/batch", "/v1/measurements/batch")}
    assert rows_b == needs_admin   # 관리자 키가 필요한 것은 B 절에, 나머지는 A 절에
    assert f"({len(actual)}개)" in manual


def test_contract_file_matches_implementation(client):
    """계약 specs/.../contracts/openapi.yaml 의 (방식, 경로) 가 실제 앱 명세와 정확히 같다 — 계약이 뒤처지지 않게 (SAD 2026-09-29)."""
    from pathlib import Path
    import yaml
    spec = Path(__file__).resolve().parents[2] / "specs/001-crowd-vacancy-api/contracts/openapi.yaml"
    c = yaml.safe_load(spec.read_text(encoding="utf-8"))
    contract = {(m.upper(), p) for p, ms in c["paths"].items() for m in ms if m in ("get", "post", "put", "patch", "delete")}
    actual = {(m.upper(), p) for p, ms in client.app.openapi()["paths"].items() for m in ms}
    assert contract == actual, f"계약에 없음 {sorted(actual - contract)} / 계약에만 있음 {sorted(contract - actual)}"
