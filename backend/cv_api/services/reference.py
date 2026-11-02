"""P2 카메라·차량 투입 등록 — 카메라 등록(R9), ROI(UC6), 제원(UC7), 매핑(UC12, CSV A1), G3·G8·G9·G12."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from shapely.geometry import Polygon
from shapely.validation import explain_validity
from sqlalchemy.exc import IntegrityError

from .. import db
from ..external import get_providers
from ..gates import GateBlocked, resolve_gate_events
from ..predict import polygon_from_text, polygon_to_text
from ..repo import diagnosis as drepo
from ..repo import measurement as mrepo
from ..repo import reference as rrepo
from ..settings import Settings, get_settings


def _camera_status(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "camera_id": row["camera_id"], "place_type": row["place_type"], "route_id": row.get("route_id"), "stop_id": row.get("stop_id"),
        "vehicle_type_id": row.get("vehicle_type_id"), "has_roi": bool(row["has_roi"]), "roi_stale": bool(row["roi_stale"]),
        "has_capacity": bool(row["has_capacity"]), "has_mapping": bool(row["has_mapping"]), "vehicle_id": row.get("vehicle_id"),
        "capacity": int(row["capacity"]) if row.get("capacity") else None, "powered": bool(row.get("powered")),
    }


def camera_status(camera_id: str) -> Dict[str, Any]:
    with db.connect() as conn:
        row = rrepo.camera_readiness(conn, camera_id)
    if not row:
        raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404, subject_kind="camera", subject_id=camera_id)
    return _camera_status(row)


def list_cameras() -> List[Dict[str, Any]]:
    with db.connect() as conn:
        return [_camera_status(r) for r in rrepo.all_camera_readiness(conn)]


def register_camera(body: Dict[str, Any], by: str) -> Dict[str, Any]:
    with db.connect() as conn:
        if rrepo.camera_readiness(conn, body["camera_id"]):
            raise GateBlocked("G8", "CAMERA_EXISTS", f"이미 등록된 카메라: {body['camera_id']}", "self", 422, record=False)
        if body.get("route_id") and not rrepo.route_exists(conn, body["route_id"]):
            raise GateBlocked("G8", "ROUTE_NOT_FOUND", f"노선이 기준 정보에 없다: {body['route_id']}", "self", 422, record=False)
        if body.get("stop_id") and not rrepo.stop_row(conn, body["stop_id"]):
            raise GateBlocked("G8", "STOP_NOT_FOUND", f"정류장이 기준 정보에 없다: {body['stop_id']}", "self", 422, record=False)
        if body.get("vehicle_type_id"):
            rrepo.upsert_vehicle_type(conn, body["vehicle_type_id"], body["vehicle_type_id"])
        rrepo.insert_camera(conn, {
            "camera_id": body["camera_id"], "place_type": body["place_type"], "route_id": body.get("route_id"), "stop_id": body.get("stop_id"),
            "vehicle_type_id": body.get("vehicle_type_id"), "roi_stale": 0, "registered_at": db.now_iso(), "registered_by": by,
        })
        resolve_gate_events(conn, "G3", "camera", body["camera_id"], by, "camera:registered")
        return _camera_status(rrepo.camera_readiness(conn, body["camera_id"]))


# ---- ROI ----
def _roi_out(r: Dict[str, Any]) -> Dict[str, Any]:
    pts = [[float(x) for x in p.split(",")] for p in r["polygon"].split()]
    return {**r, "polygon": pts, "roi_stale": None}


def roi_history(camera_id: str) -> List[Dict[str, Any]]:
    with db.connect() as conn:
        if not rrepo.camera_readiness(conn, camera_id):
            raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404, subject_kind="camera", subject_id=camera_id)
        return [_roi_out(r) for r in rrepo.roi_history(conn, camera_id)]


def save_roi(camera_id: str, body: Dict[str, Any], by: str) -> Dict[str, Any]:
    pts = body["polygon"]
    poly = Polygon([(float(x), float(y)) for x, y in pts])
    details = []
    if len(pts) < 3:
        details.append({"field": "polygon", "reason": "꼭짓점 3개 이상"})
    if not poly.is_valid:
        details.append({"field": "polygon", "reason": f"다각형 무효 — {explain_validity(poly)}"})   # 변 교차 (UC6 E1)
    if poly.area <= 0:
        details.append({"field": "polygon", "reason": "면적 0"})
    if any(x < 0 or y < 0 for x, y in pts):
        details.append({"field": "polygon", "reason": "프레임 범위 밖(음수 좌표)"})
    if details:
        raise GateBlocked("G8", "ROI_INVALID", "저장 거부 — " + "; ".join(d["reason"] for d in details), "self", 422, details=details, record=False)
    with db.connect() as conn:
        cam = rrepo.camera_readiness(conn, camera_id)
        if not cam:
            raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404, subject_kind="camera", subject_id=camera_id)
        now = db.now_iso()
        rrepo.supersede_roi(conn, camera_id, now)
        try:
            roi_id = rrepo.insert_roi(conn, {
            "camera_id": camera_id, "polygon": polygon_to_text(pts), "vertex_count": len(pts), "area": round(poly.area, 2),
            "roi_area_m2": body.get("roi_area_m2"), "footprint_m2": body.get("footprint_m2"),
            "effective_from": body["effective_from"], "superseded_at": None, "created_at": now, "created_by": by,
            })
        except IntegrityError as e:
            raise GateBlocked("G8", "ROI_DUPLICATE_VERSION", f"같은 유효 시작일({body['effective_from']})의 ROI 판본이 이미 있다 — 시작일을 바꾼다", "self", 422, record=False) from e
        rrepo.clear_roi_stale(conn, camera_id)                                   # UC6 A2
        resolve_gate_events(conn, "G4", "camera", camera_id, by, f"roi:{roi_id}")
        drepo.invalidate_runs(conn, f"roi changed: {camera_id}", now)             # H8 만료
        return _roi_out(rrepo.roi_by_id(conn, roi_id))


# ---- 차량 제원 ----
def save_spec(vehicle_type_id: str, body: Dict[str, Any], by: str) -> Dict[str, Any]:
    details = []
    if body["capacity"] <= 0:
        details.append({"field": "capacity", "reason": "양의 정수"})
    if body.get("seat_count") is not None and body["seat_count"] > body["capacity"]:
        details.append({"field": "seat_count", "reason": "좌석 수 ≤ 정원"})
    if not (body.get("source") or "").strip():
        details.append({"field": "source", "reason": "출처 필수 (BR-CV-16)"})
    if details:
        raise GateBlocked("G8", "SPEC_INVALID", "저장 거부 — " + "; ".join(d["reason"] for d in details), "self", 422, details=details, record=False)
    with db.connect() as conn:
        rrepo.upsert_vehicle_type(conn, vehicle_type_id, vehicle_type_id)
        now = db.now_iso()
        rrepo.supersede_spec(conn, vehicle_type_id, now)
        try:
            spec_id = rrepo.insert_spec(conn, {
                "vehicle_type_id": vehicle_type_id, "capacity": body["capacity"], "seat_count": body.get("seat_count"), "source": body["source"],
                "effective_from": body["effective_from"], "superseded_at": None, "created_at": now, "created_by": by,
            })
        except IntegrityError as e:
            raise GateBlocked("G8", "SPEC_DUPLICATE_VERSION", f"같은 유효 시작일({body['effective_from']})의 제원 판본이 이미 있다 — 시작일을 바꾼다", "self", 422, record=False) from e
        for cam in db.q(conn, "SELECT camera_id FROM camera WHERE vehicle_type_id=:v", v=vehicle_type_id):
            resolve_gate_events(conn, "G7", "camera", cam["camera_id"], by, f"spec:{spec_id}")
        row = rrepo.spec_by_id(conn, spec_id)
        row["affected_cameras"] = rrepo.cameras_of_type(conn, vehicle_type_id)
        return row


# ---- 매핑 ----
def _mapping_out(conn, m: Dict[str, Any]) -> Dict[str, Any]:
    sib = [x["camera_id"] for x in rrepo.active_mappings_by_vehicle(conn, m["vehicle_id"]) if x["camera_id"] != m["camera_id"]]
    return {**m, "sibling_cameras": sib}


def list_mappings(vehicle_id: Optional[str], camera_id: Optional[str]) -> List[Dict[str, Any]]:
    with db.connect() as conn:
        return [_mapping_out(conn, m) for m in rrepo.active_mappings(conn, vehicle_id, camera_id)]


def _verify_vehicle(route_id: Optional[str], vehicle_id: str, s: Settings) -> str:
    """G9 존재 검증 → 'verified' | 'unverified'(연계 장애, R11) | raise(없음)."""
    if not route_id:
        return "unverified"
    res = get_providers(s).fleet.vehicles(route_id)
    if res.source_status != "ok":
        return "unverified"
    if vehicle_id not in {v.vehicle_id for v in res.vehicles}:
        raise GateBlocked("G9", "VEHICLE_NOT_IN_FLEET", f"운행 정보에 없는 차량 번호: {vehicle_id} (노선 {route_id})", "self", 422, record=False)
    return "verified"


def save_mapping(body: Dict[str, Any], by: str, method: str = "select", s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    with db.connect() as conn:
        cam = rrepo.camera_readiness(conn, body["camera_id"])
        if not cam:
            raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {body['camera_id']}", "operator", 404, subject_kind="camera", subject_id=body["camera_id"])
        if cam["has_mapping"]:
            raise GateBlocked("G9", "CAMERA_ALREADY_MAPPED", f"카메라 {body['camera_id']} 는 이미 {cam['vehicle_id']} 에 연결되어 있다 — 해제 후 재등록", "self", 422, record=False)
        status = _verify_vehicle(cam.get("route_id"), body["vehicle_id"], s)
        now = db.now_iso()
        if body.get("vehicle_type_id"):
            rrepo.upsert_vehicle_type(conn, body["vehicle_type_id"], body["vehicle_type_id"])
        try:
            map_id = rrepo.insert_mapping(conn, {
                "camera_id": body["camera_id"], "vehicle_id": body["vehicle_id"], "vehicle_type_id": body.get("vehicle_type_id"),
                "verify_status": status, "verified_at": now if status == "verified" else None, "effective_from": now, "released_at": None,
                "created_at": now, "created_by": by, "input_method": method,
            })
        except IntegrityError as e:
            raise GateBlocked("G9", "CAMERA_ALREADY_MAPPED", "같은 카메라의 활성 매핑이 이미 있다", "self", 422, record=False) from e
        resolve_gate_events(conn, "G10", "camera", body["camera_id"], by, f"map:{map_id}")
        return _mapping_out(conn, rrepo.mapping_by_id(conn, map_id))


def release_mapping(map_id: int, by: str) -> None:
    with db.connect() as conn:
        m = rrepo.mapping_by_id(conn, map_id)
        if not m or m["released_at"]:
            raise GateBlocked("G9", "MAPPING_NOT_FOUND", f"활성 매핑이 아니다: {map_id}", "self", 404, record=False)
        now = db.now_iso()
        rrepo.release_mapping(conn, map_id, now)
        mrepo.supersede_camera_measurement(conn, map_id, now)               # UC12 A3: 기존 실측은 실측 없음
        mrepo.supersede_vehicle_measurement(conn, m["vehicle_id"], now)


def import_csv(data: bytes, by: str, s: Optional[Settings] = None) -> Dict[str, Any]:
    """UC12 A1: UTF-8(BOM 허용), 첫 행 열 이름, 필수 camera_id·vehicle_id, 선택 vehicle_type. 행별 격리."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise GateBlocked("G9", "CSV_ENCODING", "CSV 인코딩은 UTF-8 이어야 한다", "self", 422, record=False) from e
    reader = csv.DictReader(io.StringIO(text))
    cols = [c.strip() for c in (reader.fieldnames or [])]
    missing = [c for c in ("camera_id", "vehicle_id") if c not in cols]
    if missing:
        raise GateBlocked("G9", "CSV_COLUMNS_MISSING", f"필수 열 누락: {', '.join(missing)} — 허용 양식: 첫 행 열 이름, camera_id, vehicle_id, (선택) vehicle_type",
                          "self", 422, record=False)
    rows, saved, rejected = [], 0, 0
    for i, r in enumerate(reader, start=1):
        body = {"camera_id": (r.get("camera_id") or "").strip(), "vehicle_id": (r.get("vehicle_id") or "").strip(),
                "vehicle_type_id": (r.get("vehicle_type") or r.get("vehicle_type_id") or "").strip() or None}
        if not body["camera_id"] or not body["vehicle_id"]:
            rows.append({"row": i, **{k: body[k] for k in ("camera_id", "vehicle_id")}, "status": "rejected", "reason": "필수 값 없음"}); rejected += 1
            continue
        try:
            save_mapping(body, by, method="csv", s=s)
            rows.append({"row": i, "camera_id": body["camera_id"], "vehicle_id": body["vehicle_id"], "status": "saved", "reason": None}); saved += 1
        except GateBlocked as g:
            rows.append({"row": i, "camera_id": body["camera_id"], "vehicle_id": body["vehicle_id"], "status": "rejected", "reason": f"{g.gate} {g.reason}"}); rejected += 1
    return {"saved": saved, "rejected": rejected, "rows": rows}


def fleet(route_id: str, q: Optional[str], s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    res = get_providers(s).fleet.vehicles(route_id, q)
    return {"source_status": res.source_status, "fetched_at": db.now_iso(),
            "vehicles": [{"vehicle_id": v.vehicle_id, "route_id": v.route_id, "vehicle_type_id": v.vehicle_type_id} for v in res.vehicles]}
