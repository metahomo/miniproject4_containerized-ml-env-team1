"""Prometheus 지표 (GET /metrics) — 내부 포트(9524)에서만 답하고, 외부 공개 포트(9544)로는 404.
요청 수는 라우트 틀로 묶이고, 진단 결과 등급이 세어진다. openapi 에 나오지 않아 API 안내 대조(G17)와 무관하다."""
from fastapi.testclient import TestClient

from tests.helpers import KEY, make_frame

PERSON = lambda x, c=0.9: (x, 260.0, x + 70.0, 620.0, c)   # 발 위치 y=620 → ROI(300~680) 안 (test_diagnose 와 같다)  # noqa: E731


def _on(client, port):
    """같은 앱에 다른 포트로 들어온 것처럼 — scope['server'] 의 포트가 바뀐다."""
    return TestClient(client.app, base_url=f"http://testserver:{port}")


def test_metrics_only_on_internal_port(client):
    inner = _on(client, 9524).get("/metrics")
    assert inner.status_code == 200
    assert inner.headers["content-type"].startswith("text/plain")
    assert "cv_detector_loaded 1.0" in inner.text           # stub 픽스처가 적재를 마쳤다
    assert "cv_bis_calls_today" in inner.text
    assert _on(client, 9544).get("/metrics").status_code == 404       # 외부 공개 포트
    assert _on(client, 9544).get("/API/metrics").status_code == 404   # 공개 주소 접두사로 와도 막힌다


def test_requests_counted_by_route_template(client):
    c = _on(client, 9524)
    c.get("/v1/readiness")
    c.get("/no/such/path")
    c.get("/v1/reference/cameras/CAM-B12", headers=KEY)
    text = c.get("/metrics").text
    assert 'route="/v1/readiness",status="200"' in text
    assert 'route="unmatched",status="404"' in text            # 없는 경로는 하나로 묶는다
    assert 'route="/v1/reference/cameras/{camera_id}"' in text # 실제 카메라 ID 가 라벨에 들어가지 않는다
    assert "CAM-B12" not in text
    assert 'route="/metrics"' not in text                      # 수집 요청 자체는 세지 않는다


def test_diagnosis_level_counted(client, stub):
    stub.boxes = [PERSON(200), PERSON(400), PERSON(600)]
    r = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    assert r.status_code == 200 and r.json()["crowding_level"] == "free"
    text = _on(client, 9524).get("/metrics").text
    line = next(ln for ln in text.splitlines() if ln.startswith('cv_diagnoses_total{level="free"}'))
    assert float(line.split()[-1]) >= 1


def test_metrics_not_in_api_contract(client):
    assert "/metrics" not in client.app.openapi()["paths"]