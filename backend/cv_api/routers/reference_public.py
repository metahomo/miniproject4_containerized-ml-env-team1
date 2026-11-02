"""이용자 조회 경로 (T095 이용자/관리자 인증) — 호출 키(X-API-Key)로 읽기만 한다. 변경은 모두 /v1/admin/* (관리자 키, G1).

본 웹서비스 이용자(UC_00 §4)는 관리자 키 없이 S0·S5·S6·S7·S9 를 쓴다. 그 화면이 표시에 필요한 기준 정보
(카메라 목록·현재 정원·현재 ROI·현재 등급 기준·운영 상태 요약)를 여기서 준다. 개인 정보·키·이력은 없다.
`/v1/auth/whoami` 는 웹 화면의 «관리자 로그인»이 입력한 키를 확인하는 데 쓴다.
"""
from __future__ import annotations

from typing import List, Optional

import re

from fastapi import APIRouter, Depends, Header, Query

from .. import db
from ..auth import get_principal, require_caller, require_perm
from ..gates import GateBlocked
from ..repo import policy as prepo
from ..rbac import ROLE_LABEL, Principal, permissions_of
from ..schemas import CameraStatus, OpsStatus, Roi, VehicleStatus
from ..services import diagnosis, next_vehicle, reference
from ..settings import Settings, get_settings

_READ = [Depends(require_perm("reference_read"))]   # 권한 매트릭스(S10) — 기준 정보 보기

router = APIRouter(prefix="/v1", tags=["reference"], dependencies=[Depends(require_caller)])


@router.get("/auth/whoami", summary="호출 주체 확인 — RBAC 역할(admin·controller·user·integration·webservice). 웹 로그인용 (G1)")
def whoami(p: Principal = Depends(get_principal)) -> dict:
    return {"caller_id": p.caller_id, "role": p.role, "role_label": ROLE_LABEL.get(p.role, p.role), "via": p.via,
            "login_id": p.login_id, "name": p.name, "permissions": permissions_of(p.role)}


@router.get("/reference/cameras", dependencies=_READ, response_model=List[CameraStatus], summary="카메라 목록·현재 정원 (이용자 조회)")
def cameras() -> list:
    return reference.list_cameras()


@router.get("/reference/cameras/{camera_id}", dependencies=_READ, response_model=CameraStatus, summary="카메라 현황 (이용자 조회)")
def camera(camera_id: str) -> dict:
    return reference.camera_status(camera_id)


@router.get("/reference/cameras/{camera_id}/roi", dependencies=_READ, response_model=Roi, summary="현재 ROI (이용자 조회 — 화면 윤곽 표시용)")
def current_roi(camera_id: str) -> dict:
    cur = [r for r in reference.roi_history(camera_id) if not r.get("superseded_at")]
    if not cur:
        raise GateBlocked("G4", "ROI_MISSING", f"{camera_id} 에 등록된 관심영역이 없다", "operator", 404, record=False)
    return cur[0]


@router.get("/reference/threshold", dependencies=_READ, summary="현재 등급 기준·인원 세기 기준 (이용자 조회)")
def threshold() -> dict:
    with db.connect() as conn:
        t = prepo.current_threshold(conn)
        if not t:
            raise GateBlocked("G8", "NO_THRESHOLD_POLICY", "등급 기준이 없다", "operator", 404, record=False)
        cc = db.q1(conn, "SELECT count_conf_min FROM threshold_policy WHERE policy_id=:p", p=t["policy_id"])
    return {"policy_id": t["policy_id"], "free_min_ratio": t["free_min_ratio"], "crowded_max_ratio": t["crowded_max_ratio"],
            "count_conf_min": (cc or {}).get("count_conf_min"), "effective_from": db.iso(t["effective_from"]),
            # 실제로 쓰는 인원 세기 기준 — 판본 값이 비어 있으면 설정 기본값(COUNT_CONF_MIN, 모델에 맞춘 값)
            "count_conf_min_effective": diagnosis.count_conf_min(t, get_settings())}


@router.get("/reference/ops-status", response_model=OpsStatus, summary="운영 상태 요약 (S0 — 이용자 조회)")
def ops_status() -> dict:
    from .admin import ops_status as _ops   # 같은 값 — 관리자 경로와 한 곳에서 만든다
    return _ops()


# ---- 이용자가 이름으로 찾기 (T099) — 버스 상태를 보려는 이용자는 카메라 번호·내부 코드를 몰라도 된다 ----
def _route_no(name: Optional[str]) -> str:
    return re.sub(r"\s*\(\d+\)$", "", name or "")            # "102번 (30300037)" → "102번"


def _base_name(stop_name: Optional[str]) -> str:
    return (stop_name or "").split(" (")[0]                 # "충남대학교 (온천교 방면)" → "충남대학교"


def _route_sort_key(r: dict):
    m = re.match(r"\D*(\d+)", r.get("route_name") or "")
    return (int(m.group(1)) if m else 10**9, r.get("route_name") or "", r["route_id"])


@router.get("/reference/routes", dependencies=_READ, summary="노선 목록·검색 — '102' → route_id 30300037 (이용자 조회)")
def routes(q: Optional[str] = Query(default=None, max_length=40), s: Settings = Depends(get_settings)) -> list:
    """운행 정보 공급자에 맞는 노선만: BIS 모드면 BIS 적재 노선, 아니면 시연 고정 노선."""
    src_cond = "source = 'BIS'" if s.EXTERNAL_PROVIDER == "bis" else "source <> 'BIS'"
    sql, p = f"SELECT route_id, route_name, mode FROM route WHERE {src_cond}", {}
    if q:
        sql += " AND (route_name LIKE :q OR route_id = :exact)"
        p = {"q": f"%{q.strip()}%", "exact": q.strip()}
    with db.connect() as conn:
        rows = db.q(conn, sql, **p)
    return [{**r, "route_no": _route_no(r["route_name"])} for r in sorted(rows, key=_route_sort_key)[:300]]


@router.get("/reference/stops", dependencies=_READ, summary="정류장 목록·이름 검색 — route_id 의 정류장, 또는 q='충남대' 로 노선 전체에서 (이용자 조회)")
def stops(route_id: Optional[str] = None, q: Optional[str] = Query(default=None, max_length=40), limit: int = Query(default=200, ge=1, le=500),
          s: Settings = Depends(get_settings)) -> list:
    if not route_id and not q:
        raise GateBlocked("G2", "QUERY_REQUIRED", "route_id 또는 q(정류장 이름) 중 하나는 필요하다", "self", 422, record=False)
    src_cond = "r.source = 'BIS'" if s.EXTERNAL_PROVIDER == "bis" else "r.source <> 'BIS'"
    sql = f"SELECT st.stop_id, st.route_id, r.route_name, st.stop_name FROM stop st JOIN route r ON r.route_id = st.route_id WHERE {src_cond}"
    p: dict = {}
    if route_id:
        sql += " AND st.route_id = :r"; p["r"] = route_id
    if q:
        sql += " AND st.stop_name LIKE :q"; p["q"] = f"%{q.strip()}%"
    sql += " ORDER BY st.stop_name, st.stop_id"
    with db.connect() as conn:
        rows = db.q(conn, sql, **p)
    if q:   # 방향 표시 "(○○ 방면)" 에 걸린 것은 빼고, 정류장 자체 이름으로만 찾는다
        rows = [r for r in rows if q.strip() in _base_name(r["stop_name"])]
    return [{**r, "route_no": _route_no(r["route_name"])} for r in rows[:limit]]


@router.get("/reference/stops/{stop_id}/routes", dependencies=_READ, summary="정류장에 서는 노선 — 같은 정류소에 서는 버스 번호만, 노선마다 그 노선의 stop_id (이용자 조회)")
def stop_routes(stop_id: str, s: Settings = Depends(get_settings)) -> list:
    """S7 «정류장을 누르면 그 정류장에 오는 버스 번호만» (T109). BIS 정류장 ID 는 `노선ID:정류소ID` — 정류소 ID 가 같으면 같은
    정류장(같은 방향)이다. 정류소 ID 가 없는 자료(시연 고정 노선)는 같은 정류장 이름으로 묶는다."""
    src_cond = "r.source = 'BIS'" if s.EXTERNAL_PROVIDER == "bis" else "r.source <> 'BIS'"
    base = f"SELECT st.stop_id, st.route_id, r.route_name, st.stop_name FROM stop st JOIN route r ON r.route_id = st.route_id WHERE {src_cond}"
    with db.connect() as conn:
        me = db.q1(conn, "SELECT stop_id, stop_name FROM stop WHERE stop_id = :i", i=stop_id)
        if not me:
            raise GateBlocked("G3", "STOP_NOT_FOUND", f"정류장이 없다: {stop_id}", "self", 404, record=False)
        if ":" in stop_id:
            rows = db.q(conn, base + " AND st.stop_id LIKE :pat", pat=f"%:{stop_id.split(':', 1)[1]}")
        else:
            rows = db.q(conn, base + " AND st.stop_name = :n", n=me["stop_name"])
    return [{**r, "route_no": _route_no(r["route_name"])} for r in sorted(rows, key=_route_sort_key)]


@router.get("/vehicles/{vehicle_id}", dependencies=[Depends(require_perm("next_vehicle"))], response_model=VehicleStatus, summary="버스 번호로 상태 조회 — 최신 유효 실측(인원/정원·혼잡). 없으면 no_measurement (UC2)")
def vehicle(vehicle_id: str, s: Settings = Depends(get_settings)) -> dict:
    return next_vehicle.vehicle_status(vehicle_id, s)

