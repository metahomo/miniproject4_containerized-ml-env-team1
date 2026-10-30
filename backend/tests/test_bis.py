"""T047 — BIS 공급자: 실측 응답 형식(2026-09-29)으로 도착 추정·배차·차량 목록·장애 격리 확인. 네트워크 없이 MockTransport."""
from datetime import datetime, timezone

import httpx

from cv_api.external.bis import BisProvider
from cv_api.settings import Settings

HDR = '<?xml version="1.0" encoding="UTF-8"?><ServiceResult><msgHeader><currentPage>1</currentPage><headerCd>{cd}</headerCd><headerMsg>m</headerMsg><itemCnt>1</itemCnt><itemPageCnt>{pages}</itemPageCnt></msgHeader><msgBody>{body}</msgBody></ServiceResult>'


def item(**kv):
    return "<itemList>" + "".join(f"<{k}>{v}</{k}>" for k, v in kv.items()) + "</itemList>"


ROUTE = item(ROUTE_CD="30300001", ROUTE_NO="1", ALLO_INTERVAL="12", ALLO_INTERVAL_SAT="15", ALLO_INTERVAL_SUN="20", RUN_DIST_HALF="20", RUN_TM="60")
STOPS = item(BUS_STOP_ID="42740", BUS_NODE_ID="8002736", TOTAL_DIST="0") + item(BUS_STOP_ID="42720", BUS_NODE_ID="8002941", TOTAL_DIST="5000")
BUSES = (item(PLATE_NO="대전75자1013", TOTAL_DIST="4000") + item(PLATE_NO="대전75자1103", TOTAL_DIST="1000")
         + item(PLATE_NO="대전75자1015", TOTAL_DIST="6000"))   # 1015 는 이미 지나감
PAGES = {1: item(ROUTE_CD="30300001", ROUTE_NO="1") + item(ROUTE_CD="30300103", ROUTE_NO="7"),
         2: item(ROUTE_CD="30300102", ROUTE_NO="102") + item(ROUTE_CD="30300104", ROUTE_NO="7")}


def handler(req: httpx.Request) -> httpx.Response:
    assert req.url.params["serviceKey"] == "k"
    path = req.url.path
    if path.endswith("getRouteInfoAll"):
        body, pages = PAGES[int(req.url.params["reqPage"])], 2
    elif path.endswith("getRouteInfo"):
        body, pages = ROUTE if req.url.params["busRouteId"] == "30300001" else "", 1
    elif path.endswith("getStaionByRoute"):
        body, pages = STOPS, 1
    elif path.endswith("getBusPosByRtid"):
        body, pages = BUSES, 1
    else:
        return httpx.Response(404)
    return httpx.Response(200, text=HDR.format(cd=0, pages=pages, body=body))


NOW = datetime(2026, 9, 29, 0, 0, 0, tzinfo=timezone.utc)   # KST 화요일 09:00


def prov(h=handler, clock=NOW):
    return BisProvider(Settings(BIS_API_KEY="k"), transport=httpx.MockTransport(h), clock=lambda: clock)


def test_arrivals_estimated_from_distance():
    r = prov().next_arrivals("30300001", "42720", 3)
    assert r.source_status == "ok"
    # 20 km/h = 333.3 m/분 → 1000m 3분, 4000m 12분. 지나간 차량 제외, 가까운 순
    assert [(a.vehicle_id, a.expected_arrival_at) for a in r.arrivals] == [
        ("대전75자1013", "2026-09-29T00:03:00"), ("대전75자1103", "2026-09-29T00:12:00")]
    assert prov().next_arrivals("30300001", "8002941", 1).arrivals[0].vehicle_id == "대전75자1013"   # 노드 ID 도 허용


def test_route_no_resolved_and_unknown():
    assert prov().next_arrivals("1", "42720", 3).source_status == "ok"          # 노선 번호 → ROUTE_CD (2쪽 조회)
    assert prov().next_arrivals("999", "42720", 3).source_status == "no_vehicle"
    assert prov().headway("7").source_status == "none"          # 번호가 두 노선에 겹치면 추측하지 않는다
    assert prov().next_arrivals("30300001", "00000", 3).source_status == "no_vehicle"


def test_headway_by_kst_day():
    assert prov().headway("30300001").headway_minutes == 12
    assert prov(clock=datetime(2026, 10, 3, 1, tzinfo=timezone.utc)).headway("30300001").headway_minutes == 15   # 토
    assert prov(clock=datetime(2026, 10, 4, 1, tzinfo=timezone.utc)).headway("30300001").headway_minutes == 20   # 일
    assert prov().headway("30300999").source_status == "none"


def test_fleet_and_filter():
    r = prov().vehicles("30300001")
    assert r.source_status == "ok" and len(r.vehicles) == 3
    assert [v.vehicle_id for v in prov().vehicles("30300001", "1013").vehicles] == ["대전75자1013"]


def test_failures_isolated():
    def boom(req):
        raise httpx.ConnectTimeout("t", request=req)
    assert prov(boom).next_arrivals("30300001", "42720", 3).source_status == "timeout"
    assert prov(boom).headway("30300001").source_status == "timeout"
    assert prov(boom).vehicles("30300001").source_status == "unavailable"
    err = lambda req: httpx.Response(200, text=HDR.format(cd=30, pages=1, body=""))   # noqa: E731 — 인증키 오류 등
    assert prov(err).next_arrivals("30300001", "42720", 3).source_status == "unavailable"
    assert prov(lambda req: httpx.Response(500)).vehicles("30300001").source_status == "unavailable"
    assert BisProvider(Settings(BIS_API_KEY="")).next_arrivals("1", "1", 1).source_status == "unavailable"


def test_positions_cached():
    calls = []
    def h(req):
        calls.append(req.url.path)
        return handler(req)
    p = prov(h)
    p.vehicles("30300001"); p.vehicles("30300001")
    assert sum(c.endswith("getBusPosByRtid") for c in calls) == 1


def test_composite_stop_id_and_reference_csv(tmp_path, monkeypatch):
    """결정 D5: 기준 정보는 route_id=ROUTE_CD, stop_id=ROUTE_CD:BUS_STOP_ID 로 적재하고 공급자가 그 형식을 읽는다."""
    from cv_api.tools import fetch_bis_reference as fb
    assert prov().next_arrivals("30300001", "30300001:42720", 1).arrivals[0].vehicle_id == "대전75자1013"
    monkeypatch.setattr(fb, "BisProvider", lambda s: prov())
    n = fb.main(["--routes", "30300001", "--out-dir", str(tmp_path)])
    assert n == {"routes": 1, "stops": 2}
    stops = (tmp_path / "bis_stops.csv").read_text(encoding="utf-8").splitlines()
    assert stops[0] == "stop_id,route_id,stop_name,place_kind" and stops[1].startswith("30300001:42740,30300001,")
    assert "BIS" in (tmp_path / "bis_routes.csv").read_text(encoding="utf-8")


def test_calls_counted_per_day_without_cache_hits():
    from cv_api.external import bis
    before = bis.calls_today()
    p = prov()
    p.vehicles("30300001"); p.vehicles("30300001")          # 두 번째는 캐시
    assert bis.calls_today() - before == 1


def test_rate_limit_429_backs_off_and_hides_key():
    """공공데이터포털 일일 한도 초과(429): 상태 rate_limited, 5분 동안 다시 부르지 않음, 오류 문구에 인증키 없음."""
    from cv_api.external.bis import BisError
    calls = []

    def h429(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(429, text="Too Many Requests")
    s = Settings(BIS_API_KEY="SECRETKEY123", _env_file=None)
    p = BisProvider(s, transport=httpx.MockTransport(h429))
    r = p.next_arrivals("30300037", "30300037:42620", 3)
    assert r.source_status == "rate_limited" and r.arrivals == []
    n = len(calls)
    assert p.next_arrivals("30300037", "30300037:42620", 3).source_status == "rate_limited"
    assert len(calls) == n                       # 막힌 동안은 BIS 를 부르지 않는다
    try:
        p._get("busposinfo/getBusPosByRtid", busRouteId="30300037")
    except BisError as e:
        assert "SECRETKEY123" not in str(e)
    fleet = p.vehicles("30300037")
    assert fleet.source_status == "rate_limited"


def test_error_message_masks_service_key():
    from cv_api.external.bis import BisError

    def h500(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="err")
    p = BisProvider(Settings(BIS_API_KEY="SECRETKEY123", _env_file=None), transport=httpx.MockTransport(h500))
    try:
        p._get("busposinfo/getBusPosByRtid", busRouteId="30300037")
        raise AssertionError("BisError 기대")
    except BisError as e:
        assert e.status == "unavailable" and "SECRETKEY123" not in str(e) and "serviceKey=***" in str(e)


def test_route_label_type_and_endpoints():
    """같은 번호 노선을 구분하게 노선 이름에 유형(확인된 급행·간선·지선만)·기점↔반환점을 붙인다 (2026-09-30)."""
    from cv_api.tools.fetch_bis_reference import route_label
    seq = [{"BUS_STOP_ID": "1", "BUSSTOP_NM": "원내동공영차고지"}, {"BUS_STOP_ID": "2", "BUSSTOP_NM": "서대전역"}, {"BUS_STOP_ID": "3", "BUSSTOP_NM": "대전역"}]
    assert route_label({"ROUTE_CD": "30300100", "ROUTE_NO": "1", "ROUTE_TP": "1", "START_STOP_ID": "1", "TURN_STOP_ID": "3"}, seq) == "1번 · 급행 · 원내동공영차고지↔대전역 (30300100)"
    # 유형 코드 미확인(5) → 유형 없이, 반환점이 없으면 경유 순서의 가운데 정류소
    assert route_label({"ROUTE_CD": "30300001", "ROUTE_NO": "1", "ROUTE_TP": "5", "START_STOP_ID": "1"}, seq) == "1번 · 원내동공영차고지↔서대전역 (30300001)"
    assert route_label({"ROUTE_CD": "9", "ROUTE_NO": "7"}, []) == "7번 (9)"
