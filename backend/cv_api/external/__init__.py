"""외부 운행 정보 공급자 — research R12. NFR-08 격리: 이 패키지 밖으로 예외를 내지 않고 source_status 로 알린다."""
from __future__ import annotations

from ..settings import Settings, get_settings
from .base import ArrivalProvider, FleetProvider, HeadwayProvider, Providers
from .fixture import FixtureProvider

_providers: Providers | None = None


def get_providers(s: Settings | None = None) -> Providers:
    global _providers
    if _providers is None:
        s = s or get_settings()
        if s.EXTERNAL_PROVIDER == "bis":
            from .bis import BisProvider

            p = BisProvider(s)
        else:
            p = FixtureProvider(s.FIXTURES_DIR)
        _providers = Providers(arrival=p, headway=p, fleet=p)
    return _providers


def set_providers(p: Providers | None) -> None:
    global _providers
    _providers = p


__all__ = ["ArrivalProvider", "HeadwayProvider", "FleetProvider", "Providers", "FixtureProvider", "get_providers", "set_providers"]
