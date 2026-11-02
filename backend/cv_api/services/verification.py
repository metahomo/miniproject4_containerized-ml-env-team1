"""P4 정확도 검증 — 일괄 진단(UC4, 단건 모듈 반복) 과 SC-01·02 판정(H8)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .. import db
from ..gates import GateBlocked
from ..repo import diagnosis as drepo
from ..repo import reference as rrepo
from ..predict import map_level
from ..settings import Settings, get_settings
from . import diagnosis, ops


def run_batch(camera_id: str, payloads: List[Tuple[int, bytes]], admin: str, s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    ops.require_ready()
    with db.connect() as conn:
        cam = rrepo.camera_readiness(conn, camera_id)
        if not cam:
            raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404, subject_kind="camera", subject_id=camera_id)
        if not cam["has_roi"]:
            raise GateBlocked("G4", "ROI_MISSING", f"{camera_id} 에 ROI 가 없다", "operator", 409, subject_kind="camera", subject_id=camera_id, screen="S4")
        batch_id = drepo.insert_batch(conn, {"camera_id": camera_id, "purpose": "verification", "submitted_by": admin,
                                             "submitted_at": db.now_iso(), "frame_count": len(payloads)})
    items, versions, discarded, audits = [], None, 0, 0
    for seq, data in payloads:
        try:
            row = diagnosis.diagnose(data, camera_id, admin, kind="batch_item", batch_id=batch_id, batch_seq=seq, s=s, check_ready=False)
            a = diagnosis.to_assessment_schema(row)
            items.append({"seq": seq, "status": "accepted", "assessment": a})
            versions = versions or a["versions"]; discarded += 1; audits += 1
        except GateBlocked as g:
            items.append({"seq": seq, "status": "rejected", "reject": g.to_dict()}); discarded += 1
    v = versions or {"roi_id": cam["roi_id"], "spec_id": cam["spec_id"], "threshold_policy_id": 0}
    return {"batch_id": batch_id, "camera_id": camera_id, "items": items,
            "consistency": {"roi_id": v["roi_id"], "spec_id": v.get("spec_id"), "threshold_policy_id": v["threshold_policy_id"],
                            "frames_discarded": discarded, "audit_records": audits}}


def create_run(body: Dict[str, Any], admin: str) -> Dict[str, Any]:
    with db.connect() as conn:
        batch = drepo.batch_row(conn, body["batch_id"])
        if not batch:
            raise GateBlocked("G8", "BATCH_NOT_FOUND", f"일괄 묶음이 없다: {body['batch_id']}", "self", 404, record=False)
        reqs = {r["batch_seq"]: r for r in drepo.batch_requests(conn, body["batch_id"])}
        # 판본 고정: 첫 수락 결과의 정책·ROI·모델
        first = next((drepo.assessment_by_request(conn, r["request_id"]) for r in reqs.values() if r["status"] == "accepted"), None)
        if not first:
            raise GateBlocked("G8", "NO_ACCEPTED_FRAMES", "판정할 수락 프레임이 없다", "self", 422, record=False)
        now = db.now_iso()
        # 임시 run 행에 항목을 넣고 뷰로 일치율을 계산한다 (verdict 는 CHECK 제약과 일치해야 하므로 계산 후 확정)
        matches_r = matches_l = total = 0
        rows_view = []
        for it in body["items"]:
            r = reqs.get(it["seq"])
            if not r:
                continue
            a = drepo.assessment_by_request(conn, r["request_id"])
            excluded = r["status"] == "rejected" or a is None or a["crowding_level"] == "uncertain"
            ai = _counts(conn, a["assessment_id"]) if a else None
            if it.get("manual_persons") is not None:
                it = {**it, **_from_persons(it["manual_persons"], ai)}
            item = {"seq": it["seq"], "vacant_capacity_ratio": a["vacant_capacity_ratio"] if a else None,
                    "crowding_level": a["crowding_level"] if a else None, "manual_ratio": it.get("manual_ratio"),
                    "manual_level": it.get("manual_level"), "excluded": excluded}
            if ai:
                item.update(person_count=ai["person_count"], capacity=ai["capacity"])
            if it.get("manual_persons") is not None:
                item["manual_persons"] = it["manual_persons"]
                if ai and ai["person_count"] is not None:
                    item["persons_diff"] = int(ai["person_count"]) - int(it["manual_persons"])   # + 면 더 셈, - 면 놓침
            if a and it.get("manual_ratio") is not None:
                item["ratio_diff"] = round(a["vacant_capacity_ratio"] - it["manual_ratio"], 2)
            if not excluded and it.get("manual_ratio") is not None and it.get("manual_level"):
                total += 1
                matches_r += int(abs(a["vacant_capacity_ratio"] - it["manual_ratio"]) <= 10)   # SC-01 ±10%p
                matches_l += int(a["crowding_level"] == it["manual_level"])                      # SC-02
            rows_view.append((r["request_id"], it, item))
        rr = round(100.0 * matches_r / total, 2) if total else 0.0
        lr = round(100.0 * matches_l / total, 2) if total else 0.0
        verdict = "pass" if (rr >= 85 and lr >= 85) else "fail"
        run_id = drepo.insert_verification_run(conn, {
            "batch_id": body["batch_id"], "threshold_policy_id": first["threshold_policy_id"], "roi_id": first["roi_id"],
            "model_package_id": first["model_package_id"], "ratio_match_rate": rr, "level_match_rate": lr, "verdict": verdict,
            "created_at": now, "invalidated_at": None, "invalidated_reason": None,
        })
        for request_id, it, _ in rows_view:
            drepo.insert_verification_item(conn, {"run_id": run_id, "request_id": request_id, "manual_ratio": it.get("manual_ratio"), "manual_level": it.get("manual_level")})
        mp = db.q1(conn, "SELECT commit_hash FROM model_package WHERE model_package_id=:m", m=first["model_package_id"])
    return {"run_id": run_id, "batch_id": body["batch_id"], "ratio_match_rate": rr, "level_match_rate": lr, "verdict": verdict,
            "versions": {"threshold_policy_id": first["threshold_policy_id"], "roi_id": first["roi_id"], "model_commit": (mp or {}).get("commit_hash")},
            "items": [x[2] for x in rows_view]}


def _counts(conn, assessment_id: int) -> Optional[Dict[str, Any]]:
    """그 판정의 AI 인원·정원·등급 기준 (판본 고정 — 판정 당시의 정원·등급 기준)."""
    return db.q1(conn, """SELECT a.person_count, s.capacity, t.free_min_ratio, t.crowded_max_ratio
                          FROM assessment a LEFT JOIN vehicle_spec s ON s.spec_id = a.spec_id
                          LEFT JOIN threshold_policy t ON t.policy_id = a.threshold_policy_id
                          WHERE a.assessment_id = :a""", a=assessment_id)


def _from_persons(persons: int, ai: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """사람이 센 인원 → 잔여 %·등급 (R22: 잔여 = 100 − 인원 ÷ 정원, 0 에서 멈춤). 정원이 없으면 만들 수 없다 → 판정에서 빠진다."""
    if not ai or not ai.get("capacity"):
        return {"manual_ratio": None, "manual_level": None}
    ratio = round(max(0.0, 100.0 - persons / int(ai["capacity"]) * 100.0), 2)
    return {"manual_ratio": ratio, "manual_level": map_level(ratio, ai["free_min_ratio"], ai["crowded_max_ratio"])}
