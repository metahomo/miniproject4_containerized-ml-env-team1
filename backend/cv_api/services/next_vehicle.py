"""P7 후속 차량 여유도 안내 — 7.2 기준 정보(G11) → 7.3 운행 정보(G12) → 7.4 실측 판정(G13, 뷰) → 7.5 고지·시연 → 7.6 반환."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .. import db
from ..external import get_providers
from ..gates import GateBlocked
from ..repo import measurement as mrepo
from ..repo import policy as prepo
from ..repo import reference as rrepo
from ..settings import Settings, get_settings
from . import ops


def query(route_id: str, stop_id: str, limit: int = 3, s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    ops.require_ready()
    with db.connect() as conn:
        if not rrepo.route_exists(conn, route_id):
            raise GateBlocked("G11", "ROUTE_NOT_FOUND", f"노선 {route_id} 이 기준 정보(TAGO)에 없다", "self", 404, subject_kind="route_stop", subject_id=f"{route_id}/{stop_id}")
        stop = rrepo.stop_row(conn, stop_id, route_id)
        if not stop:
            raise GateBlocked("G11", "STOP_NOT_FOUND", f"정류장 {stop_id} 이 기준 정보(TAGO)에 없다", "self", 404, subject_kind="route_stop", subject_id=f"{route_id}/{stop_id}")
    # 7.3 외부 조회 — 예외를 밖으로 내지 않는다 (NFR-08)
    try:
        res = get_providers(s).arrival.next_arrivals(route_id, stop_id, limit)
        status, arrivals = res.source_status, res.arrivals
    except Exception as e:  # noqa: BLE001
        status, arrivals = ("timeout" if "timeout" in str(e).lower() else "unavailable"), []
    fetched_at = db.now_iso()
    vehicles = []
    with db.connect() as conn:
        rv = prepo.route_validity(conn, route_id)
        vp = prepo.current_validity(conn)
        demo_any = False
        if status != "ok":
            # DB CHECK 은 ok|unavailable|timeout|no_vehicle — 한도 초과(rate_limited) 등 새 사유는 unavailable 로 기록하고 응답에만 사유를 준다
            db_status = status if status in ("unavailable", "timeout", "no_vehicle") else "unavailable"
            mrepo.insert_arrival(conn, {"route_id": route_id, "stop_id": stop_id, "vehicle_id": None, "expected_arrival_at": None,
                                        "vehicle_type_id": None, "fetched_at": fetched_at, "source_status": db_status})
            vehicles.append({"vehicle_id": None, "expected_arrival_at": None, "basis_type": "unavailable", "warnings": []})
        for a in arrivals:
            mrepo.insert_arrival(conn, {"route_id": route_id, "stop_id": stop_id, "vehicle_id": a.vehicle_id, "expected_arrival_at": a.expected_arrival_at,
                                        "vehicle_type_id": a.vehicle_type_id, "fetched_at": fetched_at, "source_status": "ok"})
            st = mrepo.vehicle_status(conn, a.vehicle_id)          # G13 단일 판정 지점
            item: Dict[str, Any] = {"vehicle_id": a.vehicle_id, "expected_arrival_at": a.expected_arrival_at, "warnings": []}
            if st and st["is_valid"]:
                item.update(basis_type="measured", vacant_ratio=st["vacant_ratio_agg"], crowding_level=st["crowding_level_agg"],
                            persons_sum=st.get("persons_sum"), capacity=st.get("capacity"),
                            measured_at=st["measured_at"], coverage_num=st["coverage_num"], coverage_den=st["coverage_den"],
                            warnings=mrepo.warnings_for_vehicle(conn, st["vm_id"]))
                if st["partial_coverage"]:
                    item["warnings"].append({"code": "partial_coverage", "detail": f"커버리지 {st['coverage_num']}/{st['coverage_den']}"})
                demo_any = demo_any or bool(st["demo_flag"])
            else:
                item["basis_type"] = "no_measurement"               # 등급·비율 비움, 추정 없음 (BR-CV-13)
            vehicles.append(item)
    return {
        "route_id": route_id, "stop_id": stop_id, "place_kind": stop["place_kind"], "vehicles": vehicles,
        "applied_validity_minutes": int(rv["validity_minutes"]) if rv else int(vp["default_minutes"]),
        "validity_source": rv["validity_source"] if rv else "default", "notice": s.NOTICE_TEXT,
        "demo_mode": bool(vp["demo_on"]) and (not vp["demo_end_at"] or db.iso(vp["demo_end_at"]) > fetched_at) and demo_any,
        "fetched_at": fetched_at, "source_status": status,
    }


def vehicle_status(vehicle_id: str, s: Optional[Settings] = None) -> Dict[str, Any]:
    """T099 버스 번호 → 최신 유효 실측 (G13 단일 판정 지점 v_vehicle_measurement_status). 정류장·카메라를 몰라도 된다."""
    s = s or get_settings()
    with db.connect() as conn:
        st = mrepo.vehicle_status(conn, vehicle_id)
        out: Dict[str, Any] = {"vehicle_id": vehicle_id, "notice": s.NOTICE_TEXT, "warnings": []}
        if st and st["is_valid"]:
            out.update(basis_type="measured", vacant_ratio=st["vacant_ratio_agg"], crowding_level=st["crowding_level_agg"],
                       persons_sum=st.get("persons_sum"), capacity=st.get("capacity"), measured_at=db.iso(st["measured_at"]),
                       expires_at=db.iso(st["expires_at"]), coverage_num=st["coverage_num"], coverage_den=st["coverage_den"],
                       demo_mode=bool(st["demo_flag"]), warnings=mrepo.warnings_for_vehicle(conn, st["vm_id"]))
            if st["partial_coverage"]:
                out["warnings"].append({"code": "partial_coverage", "detail": f"커버리지 {st['coverage_num']}/{st['coverage_den']}"})
        else:
            out["basis_type"] = "no_measurement"
    return out

