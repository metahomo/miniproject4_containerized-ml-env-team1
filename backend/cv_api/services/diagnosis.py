"""P5 현재 프레임 진단 5.2~5.9 — 단건·일괄(P4)·실측(P6)이 모두 이 함수 하나를 호출한다 (SD_01 §7-3·§9-3).

순서: 규격 검증(G2) → 기준 정보(G3·G4·G7) → 품질 검사 → 추론(G5) → 등급(G6) → 저장 → 버퍼 폐기 → 응답.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .. import db, quality
from ..gates import GateBlocked, resolve_gate_events
from ..predict import DetectorNotReady, compute_occupancy, map_level, polygon_from_text
from ..repo import diagnosis as drepo
from ..repo import policy as prepo
from ..repo import reference as rrepo
from ..schemas import Warning, WarningCode
from ..settings import Settings, get_settings
from . import ops


@dataclass
class DecodedFrame:
    img: np.ndarray
    fmt: str
    width: int
    height: int
    size_bytes: int


def allowed_spec(s: Settings) -> Dict[str, Any]:
    return {
        "formats": list(s.IMAGE_FORMATS), "min_side": s.IMAGE_MIN_SIDE, "max_side": s.IMAGE_MAX_SIDE,
        "max_bytes": s.IMAGE_MAX_BYTES, "batch_max_frames": s.BATCH_MAX_FRAMES,
    }


def _sniff(data: bytes) -> Optional[str]:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] in (b"RIFF",) and data[8:12] == b"WEBP":
        return "webp"
    return None


def validate_and_decode(data: bytes, s: Optional[Settings] = None, *, camera_id: str = "") -> DecodedFrame:
    """UC5 / G2 / BR-CV-11. 규격 밖이면 진단 없이 GateBlocked(422)."""
    s = s or get_settings()
    spec = allowed_spec(s)

    def reject(code: str, why: str) -> GateBlocked:
        return GateBlocked("G2", code, f"반려 — {why}", "self", 422, allowed_spec=spec, record=False)

    if not data:
        raise reject("EMPTY", "프레임이 비어 있다")
    if len(data) > s.IMAGE_MAX_BYTES:
        raise reject("SIZE_EXCEEDED", f"용량 {len(data):,} B 가 한도 {s.IMAGE_MAX_BYTES:,} B 를 넘는다")
    fmt = _sniff(data)
    if fmt not in s.IMAGE_FORMATS:
        raise reject("FORMAT_NOT_SUPPORTED", f"지원 형식 아님 ({fmt or '알 수 없음'}). 허용: {', '.join(s.IMAGE_FORMATS).upper()}")
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise reject("CORRUPT", "손상된 파일 — 디코드 실패")
    h, w = img.shape[:2]
    if min(w, h) < s.IMAGE_MIN_SIDE or max(w, h) > s.IMAGE_MAX_SIDE:
        raise reject("RESOLUTION_OUT_OF_RANGE", f"해상도 {w}×{h} 가 허용 범위({s.IMAGE_MIN_SIDE}~{s.IMAGE_MAX_SIDE}) 밖")
    return DecodedFrame(img=img, fmt=fmt, width=w, height=h, size_bytes=len(data))


def _reference(conn, camera_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], Dict[str, Any]]:
    cam = rrepo.camera_readiness(conn, camera_id)
    if not cam:
        raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404,
                          subject_kind="camera", subject_id=camera_id)
    if not cam["powered"]:
        # 카메라 전원 관리(S2b): 기본 off — 운영 관리자가 켜야 진단한다
        raise GateBlocked("G4", "CAMERA_POWER_OFF", f"{camera_id} 의 진단 기능이 꺼져 있다 — 운영 관리자가 «카메라 전원 관리»에서 켠다",
                          "operator", 409, subject_kind="camera", subject_id=camera_id, screen="S2")
    if not cam["has_roi"]:
        raise GateBlocked("G4", "ROI_MISSING", f"{camera_id} 에 등록된 관심영역이 없어 진단할 수 없다", "operator", 409,
                          subject_kind="camera", subject_id=camera_id, screen="S5")
    roi = rrepo.roi_by_id(conn, int(cam["roi_id"]))
    spec = rrepo.spec_by_id(conn, int(cam["spec_id"])) if cam["spec_id"] else None
    thr = prepo.current_threshold(conn)
    if not thr:
        raise GateBlocked("G8", "NO_THRESHOLD_POLICY", "등급 기준(ThresholdPolicy)이 없다", "operator", 409,
                          subject_kind="policy", subject_id="threshold")
    return cam, roi, spec, thr


def diagnose(
    data: bytes,
    camera_id: str,
    caller_id: str,
    *,
    kind: str = "single",
    captured_at: Optional[str] = None,
    batch_id: Optional[int] = None,
    batch_seq: Optional[int] = None,
    s: Optional[Settings] = None,
    check_ready: bool = True,
) -> Dict[str, Any]:
    """UC1 전체. 반환: v_assessment 행 + warnings 목록 + versions (Assessment 응답 조립용)."""
    s = s or get_settings()
    if check_ready:
        ops.require_ready()
    t_start = time.perf_counter()
    received_at = db.now_iso()

    # 5.3 규격 (G2) — 반려는 요청 행으로 남긴다 (사유 포함)
    try:
        frame = validate_and_decode(data, s, camera_id=camera_id)
    except GateBlocked as g:
        with db.connect() as conn:
            if rrepo.camera_readiness(conn, camera_id):
                drepo.insert_request(conn, {
                    "kind": kind, "caller_id": caller_id, "camera_id": camera_id, "batch_id": batch_id, "batch_seq": batch_seq,
                    "captured_at": captured_at, "image_format": None, "width": None, "height": None, "size_bytes": len(data),
                    "received_at": received_at, "responded_at": db.now_iso(), "status": "rejected", "reject_reason": g.reason[:200],
                })
        raise

    # 5.4 기준 정보 (G3·G4·G7)
    with db.connect() as conn:
        cam, roi, spec, thr = _reference(conn, camera_id)
        request_id = drepo.insert_request(conn, {
            "kind": kind, "caller_id": caller_id, "camera_id": camera_id, "batch_id": batch_id, "batch_seq": batch_seq,
            "captured_at": captured_at, "image_format": frame.fmt, "width": frame.width, "height": frame.height,
            "size_bytes": frame.size_bytes, "received_at": received_at, "responded_at": None, "status": "accepted", "reject_reason": None,
        })

    # 5.5 품질 검사
    warnings: List[Warning] = quality.check_frame(frame.img, s)

    # 5.6 추론 (G5)
    det = ops.runtime.detector
    if det is None or not det.is_loaded():
        raise GateBlocked("G5", "MODEL_NOT_LOADED", "모델 적재·웜업 미완료", "operator", 503, subject_kind="instance", subject_id=str(ops.runtime.instance_id or 0))
    raw_unknown: Optional[str] = None                              # assessment_warning.raw_code (unknown 은 1건)
    t_inf = time.perf_counter()
    try:
        boxes = det.detect(frame.img, timeout_s=s.INFER_TIMEOUT_S)
    except DetectorNotReady as e:
        # UC13 E2: 추론 실패는 확정 수치 없이 판독 불확실 + unknown 경고 (NFR-05 준용)
        boxes = []
        warnings.append(Warning(code=WarningCode.unknown, detail=f"model_unavailable: {e}"))
        raw_unknown = "model_unavailable"
    infer_ms = int((time.perf_counter() - t_inf) * 1000)
    ops.runtime.state.last_infer_ms = infer_ms

    # 5.7 인원·혼잡도 (R22): 인원 세기 기준 이상 · ROI 안 인원 ÷ 차량 전체 정원
    poly = polygon_from_text(roi["polygon"])
    capacity = int(spec["capacity"]) if spec and spec.get("capacity") else None
    occ = compute_occupancy(boxes, poly, capacity, count_conf_min(thr, s), target=getattr(det, "target", "person"))
    # 평균 신뢰도·겹침은 셈에 든 사람만으로 — 배경·창밖의 애매한 검출이 판독 불확실을 만들지 않게
    det_warnings, mean_conf = quality.check_detections(occ.counted_boxes, s)
    warnings.extend(det_warnings)
    if raw_unknown == "model_unavailable":
        mean_conf = 0.0
    if cam["roi_stale"]:
        warnings.append(Warning(code=WarningCode.roi_stale, detail="ROI 검증 필요 — 카메라 위치·각도 변경 후 미갱신"))

    vacant = round(100.0 - occ.occupied_area_ratio, 2)
    quality_fail = raw_unknown == "model_unavailable" or any(w.code in (WarningCode.blur, WarningCode.low_light, WarningCode.backlight) for w in warnings)
    if not occ.ratio_computable:
        level = "uncertain"                                        # 정원 없음 — 인원만 산출 (G7)
        if raw_unknown is None:
            warnings.append(Warning(code=WarningCode.unknown, detail=f"정원 미등록 — 인원 {occ.persons_in_roi}명만 산출, 혼잡도 산출 불가"))
            raw_unknown = "capacity_missing"
        if mean_conf < s.CONFIDENCE_MIN and not any(w.code == WarningCode.low_confidence for w in warnings):
            warnings.append(Warning(code=WarningCode.low_confidence, detail=f"평균 신뢰도 {mean_conf:.2f} < {s.CONFIDENCE_MIN:g}"))
    elif quality_fail or mean_conf < s.CONFIDENCE_MIN:
        level = "uncertain"                                        # G6 출력 차단
        if mean_conf < s.CONFIDENCE_MIN and not any(w.code == WarningCode.low_confidence for w in warnings):
            warnings.append(Warning(code=WarningCode.low_confidence, detail=f"평균 신뢰도 {mean_conf:.2f} < {s.CONFIDENCE_MIN:g}"))
    else:
        level = map_level(vacant, thr["free_min_ratio"], thr["crowded_max_ratio"])

    # 5.8 저장·폐기
    del frame  # 원본 프레임 버퍼 참조 해제 (FR-11, BR-CV-09). 호출자도 data 를 보관하지 않는다
    processed_at = db.now_iso()
    with db.connect() as conn:
        assessment_id = drepo.insert_assessment(conn, {
            "request_id": request_id, "roi_id": roi["roi_id"], "spec_id": spec["spec_id"] if spec else None,
            "threshold_policy_id": thr["policy_id"], "model_package_id": ops.runtime.model_package_id or 1,
            "occupied_area_ratio": occ.occupied_area_ratio, "model_crowding_level": None, "crowding_level": level,
            "mean_confidence": round(mean_conf, 4), "processed_at": processed_at, "person_count": occ.persons_in_roi,
        })
        drepo.insert_warnings(conn, assessment_id, [{"code": w.code.value, "detail": w.detail,
                                                       "raw_code": (raw_unknown if w.code == WarningCode.unknown else None)} for w in warnings])
        drepo.finish_request(conn, request_id, db.now_iso())
        resolve_gate_events(conn, "G4", "camera", camera_id, "system", f"assessment:{assessment_id}")
        row = drepo.assessment_view(conn, assessment_id)
        mp = db.q1(conn, "SELECT commit_hash FROM model_package WHERE model_package_id=:m", m=row["model_package_id"])
    row["warning_list"] = [{"code": w.code.value, "detail": w.detail} for w in warnings]
    row["person_count"] = occ.persons_in_roi
    row["capacity"] = occ.capacity
    row["over_capacity"] = occ.over_capacity
    row["versions"] = {"roi_id": roi["roi_id"], "spec_id": spec["spec_id"] if spec else None,
                       "threshold_policy_id": thr["policy_id"], "model_commit": (mp or {}).get("commit_hash", "unknown")}
    row["response_ms"] = int((time.perf_counter() - t_start) * 1000)
    row["notice"] = s.NOTICE_TEXT
    row["captured_at"] = captured_at
    return row


def count_conf_min(thr: Dict[str, Any], s: Settings) -> float:
    """R22 인원 세기 기준 — 등급 기준 판본에 딸린 값. 비어 있으면(이전 판본) 설정 기본값.
    뷰(SELECT *)의 열 구성이 DBMS 마다 다를 수 있어 표에서 직접 읽는다."""
    with db.connect() as conn:
        r = db.q1(conn, "SELECT count_conf_min FROM threshold_policy WHERE policy_id=:p", p=thr["policy_id"])
    v = (r or {}).get("count_conf_min")
    return float(v) if v is not None else s.COUNT_CONF_MIN


def to_assessment_schema(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "assessment_id": row["assessment_id"], "camera_id": row["camera_id"], "captured_at": row.get("captured_at"),
        "occupied_area_ratio": row["occupied_area_ratio"], "vacant_capacity_ratio": row["vacant_capacity_ratio"],
        "crowding_level": row["crowding_level"], "is_reference_only": bool(row["is_reference_only"]),
        "person_count": int(row.get("person_count") or 0), "capacity": row.get("capacity"), "over_capacity": bool(row.get("over_capacity")),
        "remaining_persons": row.get("remaining_persons"), "remaining_not_computable": bool(row["remaining_not_computable"]),
        "mean_confidence": row["mean_confidence"], "warnings": row.get("warning_list", []), "notice": row["notice"],
        "processed_at": row["processed_at"], "response_ms": row.get("response_ms"), "versions": row["versions"],
    }
