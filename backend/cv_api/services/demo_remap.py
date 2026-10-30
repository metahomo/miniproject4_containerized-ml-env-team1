"""시연 카메라를 지금 운행 중인 BIS 차량으로 다시 연결 (T097, 시연 102번·충남대학교).

실제 BIS 로 전환한 뒤(T096) 데모 카메라의 매핑 차량은 그날 운행하지 않을 수 있다. 정류장에 곧 도착할 차량 순서대로
카메라를 다시 연결해 S6 실측 → S7 후속 차량 흐름을 바로 시연할 수 있게 한다.

- 도착 예정 차량 앞쪽 N대(N = 카메라 수)가 목표. 이미 그중 한 대에 연결된 카메라는 그대로 둔다.
- 나머지 카메라는 매핑 해제(UC12 A3 — 이전 실측은 실측 없음) 후 남은 목표 차량에 연결(G9 운행 정보 검증은 save_mapping 이 한다).
- 도착 정보가 없거나(첫차 전·막차 후) 연계 장애면 아무것도 바꾸지 않는다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .. import db
from ..external import get_providers
from ..gates import GateBlocked
from ..repo import reference as rrepo
from ..settings import Settings, get_settings
from . import reference

DEFAULT_ROUTE = "30300037"                 # 102번 (BIS ROUTE_CD)
DEFAULT_STOP = "30300037:42620"            # 충남대학교 (홈플러스유성점 방면)
DEFAULT_CAMERAS = ("CAM-DEMO-01", "CAM-DEMO-02", "CAM-DEMO-03")


def remap(by: str, route_id: str = DEFAULT_ROUTE, stop_id: str = DEFAULT_STOP, cameras: Sequence[str] = DEFAULT_CAMERAS,
          s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    with db.connect() as conn:
        if not rrepo.stop_row(conn, stop_id):
            raise GateBlocked("G11", "STOP_NOT_FOUND", f"정류장이 기준 정보에 없다: {stop_id}", "self", 404, record=False)
        current = {}
        for cam in cameras:
            c = rrepo.camera_readiness(conn, cam)
            if not c:
                raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {cam}", "operator", 404, record=False)
            m = rrepo.active_mappings(conn, None, cam)
            current[cam] = {"map": m[0] if m else None, "vehicle_type_id": (m[0].get("vehicle_type_id") if m else None) or c.get("vehicle_type_id")}

    try:
        res = get_providers(s).arrival.next_arrivals(route_id, stop_id, max(6, len(cameras) * 2))
        status, arrivals = res.source_status, res.arrivals
    except Exception as e:  # noqa: BLE001 — 연계 장애는 바꾸지 않고 알린다
        status, arrivals = "unavailable", []
        _ = e
    eta: Dict[str, Optional[str]] = {}
    for a in arrivals:
        if a.vehicle_id and a.vehicle_id not in eta:
            eta[a.vehicle_id] = a.expected_arrival_at

    def row(cam: str, before: Optional[str], after: Optional[str], action: str) -> Dict[str, Any]:
        return {"camera_id": cam, "before": before, "after": after, "expected_arrival_at": eta.get(after or ""), "action": action}

    before = {cam: (v["map"]["vehicle_id"] if v["map"] else None) for cam, v in current.items()}
    if status != "ok" or not eta:
        why = "연계 장애 — 운행 정보를 받지 못했다" if status != "ok" else "도착 예정 차량이 없다 (운행 시간 밖일 수 있다)"
        return {"route_id": route_id, "stop_id": stop_id, "source_status": status, "changed": 0, "message": f"{why}. 매핑을 바꾸지 않았다",
                "rows": [row(c, before[c], before[c], "unchanged") for c in cameras]}

    targets: List[str] = list(eta)[: len(cameras)]
    keep = {cam for cam in cameras if before[cam] in targets}
    free = [v for v in targets if v not in {before[c] for c in keep}]
    rows, changed = [], 0
    for cam in cameras:
        if cam in keep:
            rows.append(row(cam, before[cam], before[cam], "kept"))
            continue
        if not free:                      # 도착 예정 차량이 카메라 수보다 적다
            rows.append(row(cam, before[cam], before[cam], "unchanged"))
            continue
        veh = free.pop(0)
        if current[cam]["map"]:
            reference.release_mapping(int(current[cam]["map"]["map_id"]), by)
        reference.save_mapping({"camera_id": cam, "vehicle_id": veh, "vehicle_type_id": current[cam]["vehicle_type_id"]}, by, "select", s)   # input_method CHECK(select|csv) — 운행 차량 목록에서 고른 것과 같다
        rows.append(row(cam, before[cam], veh, "changed"))
        changed += 1
    return {"route_id": route_id, "stop_id": stop_id, "source_status": status, "changed": changed,
            "message": f"{changed}대 다시 연결, {len(keep)}대 그대로 (도착 예정 순)"
                       + (f" · 도착 예정 차량이 {len(eta)}대뿐이라 {short}대는 바꾸지 않았다" if (short := sum(r['action'] == 'unchanged' for r in rows)) else ""),
            "rows": rows}
