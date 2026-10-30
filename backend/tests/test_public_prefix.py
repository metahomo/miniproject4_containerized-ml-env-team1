"""T098 — 공개 API 주소 https://p4.sumzip.com/API: /API 접두사로 같은 API·Swagger, 접두사 없는 9544 직접 접근도 그대로."""
from tests.helpers import KEY, make_frame


def test_api_prefix_serves_same_api(client, stub):
    assert client.get("/API/v1/readiness").json()["readiness"] == "ready"
    a = client.post("/API/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    b = client.post("/v1/diagnose", headers=KEY, data={"camera_id": "CAM-B12"}, files={"frame": ("f.jpg", make_frame(), "image/jpeg")})
    assert a.status_code == b.status_code == 200 and a.json()["crowding_level"] == b.json()["crowding_level"]
    assert client.post("/API/v1/diagnose", data={"camera_id": "CAM-B12"}).status_code == 401   # 키 규칙도 같다


def test_swagger_under_prefix_points_to_prefixed_spec(client):
    assert "/API/openapi.json" in client.get("/API/docs").text
    assert "'/openapi.json'" in client.get("/docs").text                        # 직접 접근은 그대로
    assert client.get("/API/openapi.json").json()["servers"] == [{"url": "/API"}]   # «Try it out» → /API/v1/...
    r = client.get("/API", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/API/docs"
    assert client.get("/", follow_redirects=False).headers["location"] == "/docs"
    assert client.get("/APIX/v1/readiness").status_code == 404                   # 접두사는 경로 단위로만
