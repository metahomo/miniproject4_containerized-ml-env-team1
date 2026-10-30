"""고정 데이터 공급자 — 시연·테스트용 (research R12). data/fixtures/*.json 을 읽는다.

시연 시나리오(HG/시연웹 §1-1): 노선 R102, 정류장 3001(충남대), 차량 1234·5678·9012·3456, 배차 12분.
도착 시각은 '지금 + N분' 으로 매 조회마다 계산한다 — 발표 시각의 실제 운행에 의존하지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .base import Arrival, ArrivalResult, FleetResult, FleetVehicleRow, HeadwayResult


class FixtureProvider:
    def __init__(self, fixtures_dir: Path):
        self.dir = Path(fixtures_dir)
        self._data = None
        self.fail_arrivals = False   # 테스트에서 G12 를 흉내 낼 때

    def _load(self) -> dict:
        if self._data is None:
            p = self.dir / "transit.json"
            self._data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"routes": {}}
        return self._data

    def next_arrivals(self, route_id: str, stop_id: str, limit: int) -> ArrivalResult:
        if self.fail_arrivals:
            return ArrivalResult(source_status="unavailable")
        route = self._load()["routes"].get(route_id)
        if not route:
            return ArrivalResult(source_status="no_vehicle")
        stop = route.get("stops", {}).get(stop_id)
        if not stop:
            return ArrivalResult(source_status="no_vehicle")
        now = datetime.now(timezone.utc)
        arrivals = [
            Arrival(
                vehicle_id=a["vehicle_id"],
                expected_arrival_at=(now + timedelta(minutes=float(a["minutes"]))).strftime("%Y-%m-%dT%H:%M:%S"),
                vehicle_type_id=a.get("vehicle_type_id"),
            )
            for a in stop.get("arrivals", [])[:limit]
        ]
        return ArrivalResult(source_status="ok" if arrivals else "no_vehicle", arrivals=arrivals)

    def headway(self, route_id: str) -> HeadwayResult:
        route = self._load()["routes"].get(route_id)
        if not route or route.get("headway_minutes") is None:
            return HeadwayResult(source_status="none")
        return HeadwayResult(source_status=route.get("headway_source", "bis"), headway_minutes=int(route["headway_minutes"]))

    def vehicles(self, route_id: str, q: Optional[str] = None) -> FleetResult:
        route = self._load()["routes"].get(route_id)
        if not route:
            return FleetResult(source_status="ok", vehicles=[])
        rows = [FleetVehicleRow(vehicle_id=v["vehicle_id"], route_id=route_id, vehicle_type_id=v.get("vehicle_type_id")) for v in route.get("fleet", [])]
        if q:
            rows = [r for r in rows if q in r.vehicle_id]
        return FleetResult(source_status="ok", vehicles=rows)
