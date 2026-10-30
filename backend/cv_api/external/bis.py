"""대전광역시 BIS 공급자 — research R12, T047. 공공데이터포털(apis.data.go.kr/6300000) XML API.

사용 API (2026-09-29 인증키로 실측한 필드):
- 노선정보조회 `busRouteInfo`
  - getRouteInfo?busRouteId=  → ROUTE_CD, ROUTE_NO, ALLO_INTERVAL(_SAT/_SUN) 분, RUN_DIST_HALF km, RUN_TM 분
  - getRouteInfoAll?reqPage=  → 위 항목 전체(쪽당 100건, msgHeader.itemPageCnt) — 노선 번호 → ROUTE_CD 해석용
  - getStaionByRoute?busRouteId= → BUS_STOP_ID, BUS_NODE_ID, BUSSTOP_SEQ, TOTAL_DIST(기점부터 누적 m)
- 버스위치정보 `busposinfo/getBusPosByRtid?busRouteId=` → PLATE_NO, BUS_STOP_ID, TOTAL_DIST(누적 m), DIR, ARR_TIME
- (정류소조회 `GetStatListService/getStatList` 는 기준 정보 적재용 — 이 공급자는 쓰지 않는다)

도착 정보 API 는 제공 목록에 없다. 도착 예정 시각은 **추정**이다:
  (정류소 누적 거리 − 버스 누적 거리) ÷ 노선 평균 속도(RUN_DIST_HALF ÷ RUN_TM).
응답 헤더 headerCd != 0, HTTP 오류, 파싱 오류는 unavailable, 제한 시간 초과는 timeout 으로 알린다(NFR-08).
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

import httpx

from ..settings import Settings
from .base import Arrival, ArrivalResult, FleetResult, FleetVehicleRow, HeadwayResult

KST = timezone(timedelta(hours=9))
log = logging.getLogger("cv_api.bis")
_calls: Dict[str, int] = {}   # 한국 날짜별 실제 API 호출 수 (캐시 적중 제외) — 공공데이터포털 일일 한도 점검용


def calls_today() -> int:
    return _calls.get(datetime.now(KST).strftime("%Y-%m-%d"), 0)


class BisError(Exception):
    def __init__(self, status: str, detail: str = ""):
        super().__init__(detail or status)
        self.status = status          # unavailable | timeout | rate_limited(공공데이터포털 일일 호출 한도 초과, HTTP 429)


RATE_LIMIT_BACKOFF_S = 300.0   # 429 를 받으면 5분 동안 BIS 를 부르지 않는다 — 거부될 호출로 한도 창구를 두드리지 않게


def _mask(text: str) -> str:
    """오류 문구에 섞인 인증키(serviceKey=…)를 가린다 — httpx 오류 메시지는 요청 URL 을 그대로 담는다."""
    import re
    return re.sub(r"(serviceKey=)[^&\s']+", r"\1***", text)


class BisProvider:
    def __init__(self, s: Settings, transport: Optional[httpx.BaseTransport] = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.s = s
        self.base = s.BIS_BASE_URL.rstrip("/")
        self.key = s.BIS_API_KEY
        self.client = httpx.Client(timeout=s.BIS_TIMEOUT_S, transport=transport)
        self.clock = clock
        self._cache: Dict[Tuple[str, str], Tuple[float, object]] = {}
        self._blocked_until = 0.0   # 한도 초과(429) 후 다시 부르지 않을 때까지 (monotonic)

    # ---- 호출·파싱 ----
    def _get(self, path: str, **params) -> List[Dict[str, str]]:
        return self._get_page(path, **params)[0]

    def _get_page(self, path: str, **params) -> Tuple[List[Dict[str, str]], int]:
        if not self.key:
            raise BisError("unavailable", "BIS_API_KEY 미설정")
        if time.monotonic() < self._blocked_until:
            raise BisError("rate_limited", "BIS 일일 호출 한도 초과 — 잠시 뒤 다시 시도")
        day = datetime.now(KST).strftime("%Y-%m-%d")
        _calls[day] = _calls.get(day, 0) + 1
        log.info("BIS call %s (%s 누적 %d)", path, day, _calls[day])   # 키는 남기지 않는다
        try:
            r = self.client.get(f"{self.base}/{path}", params={**params, "serviceKey": self.key})
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except httpx.TimeoutException as e:
            raise BisError("timeout", _mask(str(e))) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self._blocked_until = time.monotonic() + RATE_LIMIT_BACKOFF_S
                log.warning("BIS 429 — 일일 호출 한도 초과, %ds 동안 호출 중지 (오늘 호출 %d)", RATE_LIMIT_BACKOFF_S, _calls.get(day, 0))
                raise BisError("rate_limited", "BIS 일일 호출 한도 초과 (공공데이터포털 429)") from None
            raise BisError("unavailable", _mask(str(e))) from None
        except (httpx.HTTPError, ET.ParseError) as e:
            raise BisError("unavailable", _mask(str(e))) from None
        cd = (root.findtext("msgHeader/headerCd") or "").strip()
        if cd not in ("0", "4"):          # 4 = 결과 없음(실측 전 가정) — 빈 목록으로 다룬다
            raise BisError("unavailable", f"headerCd={cd} {root.findtext('msgHeader/headerMsg') or root.findtext('.//returnAuthMsg') or ''}")
        pages = int((root.findtext("msgHeader/itemPageCnt") or "1").strip() or 1)
        return [{c.tag: (c.text or "").strip() for c in item} for item in root.iter("itemList")], pages

    def _cached(self, key: Tuple[str, str], ttl: float, fn: Callable[[], object]):
        hit = self._cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < ttl:
            return hit[1]
        val = fn()
        self._cache[key] = (now, val)
        return val

    def _route_codes(self) -> Dict[str, str]:
        """노선 번호(ROUTE_NO) → ROUTE_CD. 전체 노선을 쪽 단위로 받는다.
        번호는 유일하지 않다(실측: '1' 이 급행·간선·지선 3개 ROUTE_CD). 겹치는 번호는 빈 값으로 두어 추측하지 않는다."""
        def load():
            out: Dict[str, str] = {}
            page, pages = 1, 1
            while page <= pages:
                items, pages = self._get_page("busRouteInfo/getRouteInfoAll", reqPage=page)
                for it in items:
                    no = it.get("ROUTE_NO", "")
                    out[no] = "" if no in out else it.get("ROUTE_CD", "")
                page += 1
            return out
        return self._cached(("route_codes", ""), self.s.BIS_STATIC_CACHE_S, load)  # type: ignore[return-value]

    def _route_cd(self, route_id: str) -> str:
        if route_id.isdigit() and len(route_id) == 8:
            return route_id
        cd = self._route_codes().get(route_id)
        if not cd:
            raise LookupError(route_id)
        return cd

    def _route_info(self, cd: str) -> Dict[str, str]:
        items = self._cached(("route", cd), self.s.BIS_STATIC_CACHE_S, lambda: self._get("busRouteInfo/getRouteInfo", busRouteId=cd))
        if not items:
            raise LookupError(cd)
        return items[0]  # type: ignore[index]

    def _stations(self, cd: str) -> List[Dict[str, str]]:
        return self._cached(("stations", cd), self.s.BIS_STATIC_CACHE_S,  # type: ignore[return-value]
                            lambda: self._get("busRouteInfo/getStaionByRoute", busRouteId=cd))

    def _positions(self, cd: str) -> List[Dict[str, str]]:
        return self._cached(("pos", cd), self.s.BIS_POS_CACHE_S,  # type: ignore[return-value]
                            lambda: self._get("busposinfo/getBusPosByRtid", busRouteId=cd))

    def _speed_m_per_min(self, info: Dict[str, str]) -> float:
        try:
            kmh = float(info["RUN_DIST_HALF"]) / (float(info["RUN_TM"]) / 60.0)
        except (KeyError, ValueError, ZeroDivisionError):
            kmh = self.s.BIS_DEFAULT_SPEED_KMH
        kmh = min(max(kmh, 8.0), 40.0)       # 비정상 값 방어
        return kmh * 1000.0 / 60.0

    # ---- ArrivalProvider ----
    def next_arrivals(self, route_id: str, stop_id: str, limit: int) -> ArrivalResult:
        try:
            cd = self._route_cd(route_id)
            info = self._route_info(cd)
            sid = stop_id.split(":", 1)[1] if ":" in stop_id else stop_id   # 기준 정보의 합성 ID "ROUTE_CD:BUS_STOP_ID" (fetch_bis_reference)
            stops = [st for st in self._stations(cd) if sid in (st.get("BUS_STOP_ID"), st.get("BUS_NODE_ID"))]
            if not stops:
                return ArrivalResult(source_status="no_vehicle")
            buses = self._positions(cd)
        except LookupError:
            return ArrivalResult(source_status="no_vehicle")
        except BisError as e:
            return ArrivalResult(source_status=e.status)
        speed = self._speed_m_per_min(info)
        stop_dists = [float(st["TOTAL_DIST"]) for st in stops if st.get("TOTAL_DIST")]
        now = self.clock()
        cands: List[Tuple[float, str]] = []
        for b in buses:
            try:
                bd = float(b["TOTAL_DIST"])
            except (KeyError, ValueError):
                continue
            ahead = [d - bd for d in stop_dists if d - bd > 0]   # 정류소를 아직 지나지 않은 버스만
            if ahead and b.get("PLATE_NO"):
                cands.append((min(ahead), b["PLATE_NO"]))
        cands.sort()
        arrivals = [
            Arrival(vehicle_id=plate, expected_arrival_at=(now + timedelta(minutes=dist / speed)).strftime("%Y-%m-%dT%H:%M:%S"))
            for dist, plate in cands[:limit]
        ]
        return ArrivalResult(source_status="ok" if arrivals else "no_vehicle", arrivals=arrivals)

    # ---- HeadwayProvider ----
    def headway(self, route_id: str) -> HeadwayResult:
        try:
            info = self._route_info(self._route_cd(route_id))
        except LookupError:
            return HeadwayResult(source_status="none")
        except BisError as e:
            return HeadwayResult(source_status=e.status)   # policy.refresh_headways 가 stale/none 으로 바꾼다
        wd = self.clock().astimezone(KST).weekday()
        field = {5: "ALLO_INTERVAL_SAT", 6: "ALLO_INTERVAL_SUN"}.get(wd, "ALLO_INTERVAL")
        raw = info.get(field) or info.get("ALLO_INTERVAL") or ""
        try:
            minutes = int(float(raw))
        except ValueError:
            return HeadwayResult(source_status="none")
        return HeadwayResult(source_status="bis", headway_minutes=minutes) if minutes > 0 else HeadwayResult(source_status="none")

    # ---- FleetProvider — 지금 운행 중인 차량(위치 정보에 잡힌 차량) ----
    def vehicles(self, route_id: str, q: Optional[str] = None) -> FleetResult:
        try:
            cd = self._route_cd(route_id)
            buses = self._positions(cd)
        except LookupError:
            return FleetResult(source_status="ok", vehicles=[])
        except BisError as e:
            return FleetResult(source_status="unavailable" if e.status == "timeout" else e.status)
        seen, rows = set(), []
        for b in buses:
            plate = b.get("PLATE_NO")
            if plate and plate not in seen and (not q or q in plate):
                seen.add(plate)
                rows.append(FleetVehicleRow(vehicle_id=plate, route_id=route_id))
        return FleetResult(source_status="ok", vehicles=rows)
