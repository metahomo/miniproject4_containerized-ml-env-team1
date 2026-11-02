from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol


@dataclass
class Arrival:
    vehicle_id: str
    expected_arrival_at: str          # ISO UTC
    vehicle_type_id: Optional[str] = None


@dataclass
class ArrivalResult:
    source_status: str                # ok | unavailable | timeout | no_vehicle
    arrivals: List[Arrival] = field(default_factory=list)


@dataclass
class HeadwayResult:
    source_status: str                # bis | timetable | none | stale
    headway_minutes: Optional[int] = None


@dataclass
class FleetVehicleRow:
    vehicle_id: str
    route_id: str
    vehicle_type_id: Optional[str] = None


@dataclass
class FleetResult:
    source_status: str                # ok | unavailable | stale
    vehicles: List[FleetVehicleRow] = field(default_factory=list)


class ArrivalProvider(Protocol):
    def next_arrivals(self, route_id: str, stop_id: str, limit: int) -> ArrivalResult: ...


class HeadwayProvider(Protocol):
    def headway(self, route_id: str) -> HeadwayResult: ...


class FleetProvider(Protocol):
    def vehicles(self, route_id: str, q: Optional[str] = None) -> FleetResult: ...


@dataclass
class Providers:
    arrival: ArrivalProvider
    headway: HeadwayProvider
    fleet: FleetProvider
