"""P1 서버 준비 · P0 상시 운영 — 검출기 적재·웜업·계약 확인, 준비 상태(G0), 시연 자동 해제, 준비 감시, 지표, 보존.

모델 로딩 시간을 사용자·관리자 화면이 알 수 있도록 DetectorState(적재 여부·소요 초·웜업 시각·마지막 추론 ms)를 유지하고
readiness 응답에 함께 준다 (참고사항: 로딩 시간을 고려한 인터페이스).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .. import db
from ..predict import Detector, DetectorNotReady, DetectorState, build_detector, contract_self_check
from ..repo import ops as ops_repo
from ..repo import policy as policy_repo
from ..settings import BACKEND_DIR, Settings, get_settings

log = logging.getLogger("cv_api.ops")


class Runtime:
    """프로세스 전역 상태: 검출기, 인스턴스 ID, 상태."""

    def __init__(self):
        self.detector: Optional[Detector] = None
        self.state = DetectorState()
        self.instance_id: Optional[int] = None
        self.model_package_id: Optional[int] = None
        self._task: Optional[asyncio.Task] = None

    # ---- 검출기 주입 (테스트) ----
    def set_detector(self, det: Detector) -> None:
        self.detector = det
        self.state = DetectorState(kind=det.kind, model=det.model_name)


runtime = Runtime()


def _weights_record(s: Settings) -> Dict[str, Any]:
    """실제로 적재한 가중치의 판본 정보. `models/<가중치 이름>.json` 이 있으면 그것, 없으면 `model_package.json`(yolov8n) 이
    같은 파일을 가리킬 때만 그것, 그 밖에는 파일 해시로 판본을 구분한다 — 가중치를 바꿔도 진단 기록의 모델 판본이 맞게 (2026-09-30)."""
    w = s.MODEL_WEIGHTS
    side = w.with_suffix(".json")
    if side.exists():
        return json.loads(side.read_text(encoding="utf-8"))
    base = BACKEND_DIR / "models" / "model_package.json"
    rec = json.loads(base.read_text(encoding="utf-8")) if base.exists() else {}
    if rec.get("weights_file") == w.name:
        return rec
    digest = hashlib.sha256(w.read_bytes()).hexdigest()[:16] if w.exists() else "missing"
    return {"repo_url": rec.get("repo_url", s.MODEL_REPO), "commit_hash": f"weights-sha256:{digest}", "weights_file": w.name,
            "license": None, "required_versions": rec.get("required_versions")}


def _model_package_record(s: Settings, det: Detector) -> Dict[str, Any]:
    rec = _weights_record(s) if det.kind == "yolov8" else {}
    if det.kind == "ollama_vl":
        return {
            "repo_url": s.OLLAMA_URL, "commit_hash": f"ollama:{det.model_name}", "weights_file": det.model_name,
            "license": None, "required_versions": "ollama server", "contract_check_result": "adapter",
            "fetched_at": db.now_iso(), "fetched_by": "system", "detector_kind": "ollama_vl",
        }
    if det.kind == "stub":
        return {"repo_url": "stub", "commit_hash": "stub", "weights_file": "stub", "license": None, "required_versions": None,
                "contract_check_result": "adapter", "fetched_at": db.now_iso(), "fetched_by": "test", "detector_kind": "stub"}
    return {
        "repo_url": rec.get("repo_url", s.MODEL_REPO), "commit_hash": rec.get("commit_hash", "unknown"),
        "weights_file": rec.get("weights_file", s.MODEL_WEIGHTS.name), "license": rec.get("license"),
        "required_versions": rec.get("required_versions"), "contract_check_result": "adapter",
        "fetched_at": rec.get("fetched_at", db.now_iso()), "fetched_by": "op", "detector_kind": "yolov8",
    }


def startup(s: Optional[Settings] = None) -> Dict[str, Any]:
    """P1 1.3~1.4: DDL 적용 → 인스턴스 preparing → 검출기 적재 → 웜업·계약 확인 → ready. 실패해도 서버는 뜨고 G0 가 닫힌다."""
    s = s or get_settings()
    info = db.init_db()
    det = runtime.detector or build_detector(s)
    runtime.detector = det
    runtime.state = DetectorState(kind=det.kind, model=det.model_name)
    with db.connect() as conn:
        mp_id = ops_repo.upsert_model_package(conn, _model_package_record(s, det))
        runtime.model_package_id = mp_id
        runtime.instance_id = ops_repo.insert_instance(conn, {
            "model_package_id": mp_id, "endpoint_url": s.SERVER_PUBLIC_URL, "port": None, "auth_method": "api-key",
            "started_at": db.now_iso(), "readiness": "preparing", "readiness_updated_at": db.now_iso(), "detector_kind": det.kind,
        })
        _seed_defaults(conn, s)
    try:
        t0 = time.perf_counter()
        load_s = det.load()
        check = contract_self_check(det, s)
        total = time.perf_counter() - t0
        runtime.state.loaded = True
        runtime.state.load_seconds = round(load_s, 2)
        runtime.state.warmed_up_at = db.now_iso()
        runtime.state.last_infer_ms = check.get("infer_ms")
        runtime.state.contract_ok = bool(check.get("contract_ok"))
        runtime.state.note = f"적재 {load_s:.1f}s, 웜업 포함 {total:.1f}s"
        with db.connect() as conn:
            ops_repo.update_instance(conn, runtime.instance_id, {
                "warmup_done_at": db.now_iso(), "contract_ok": 1 if runtime.state.contract_ok else 0,
                "readiness": "ready" if runtime.state.contract_ok else "unavailable", "readiness_updated_at": db.now_iso(),
                "load_seconds": round(total, 2),
            })
        log.info("detector ready: %s %s (%.1fs)", det.kind, det.model_name, total)
    except (DetectorNotReady, Exception) as e:  # noqa: BLE001
        runtime.state.loaded = False
        runtime.state.note = f"적재 실패: {e}"
        with db.connect() as conn:
            ops_repo.update_instance(conn, runtime.instance_id, {"readiness": "unavailable", "readiness_updated_at": db.now_iso(), "contract_ok": 0})
        log.error("detector load failed: %s", e)
    return {"db": info, "detector": runtime.state.as_dict()}


def _seed_defaults(conn, s: Settings) -> None:
    """원천 기본값이 없는 빈 DB 에 등급 기준(50/20)·유효 시간 규칙(계수 1, 상한 30, 기본 10분)을 1회 넣는다."""
    now = db.now_iso()
    if not policy_repo.current_threshold(conn) and not policy_repo.threshold_history(conn):
        policy_repo.insert_threshold(conn, {"free_min_ratio": 50, "crowded_max_ratio": 20, "effective_from": now, "created_at": now, "created_by": "system"})
    if not policy_repo.current_validity(conn):
        policy_repo.insert_validity(conn, {
            "basis": "headway", "factor": 1.0, "cap_minutes": 30, "default_minutes": 10, "window_minutes": 1, "demo_on": 0,
            "demo_end_at": None, "effective_from": now, "created_at": now, "created_by": "system",
        }, [])


def readiness_payload() -> Dict[str, Any]:
    with db.connect() as conn:
        r = ops_repo.readiness(conn)
    if not r:
        return {"readiness": "preparing", "updated_at": db.now_iso(), "model_commit": None, "detector": runtime.state.as_dict()}
    return {
        "readiness": r["readiness"], "updated_at": r["readiness_updated_at"], "model_commit": r.get("commit_hash"),
        "detector": runtime.state.as_dict() if runtime.detector is not None else _detector_from_db(r),
    }


def _detector_from_db(r: Dict[str, Any]) -> Dict[str, Any]:
    """검출기가 이 프로세스에 없을 때(웹 백엔드 9524) — 진단 API 가 기록한 server_instance 값으로 적재 상태를 보여 준다."""
    return DetectorState(kind=r.get("detector_kind") or "", model=r.get("weights_file") or "", loaded=r["readiness"] == "ready",
                         load_seconds=r.get("load_seconds"), warmed_up_at=r.get("warmup_done_at"),
                         note="진단 API 서버(9544)의 기록").as_dict()


def require_ready() -> None:
    """G0. 준비 중/불가면 GateBlocked(503)."""
    from ..gates import GateBlocked

    with db.connect() as conn:
        r = ops_repo.readiness(conn)
    state = r["readiness"] if r else "preparing"
    if state != "ready":
        reason = ("진단 API 서버 준비 중 — 모델 적재·웜업 미완료" if state == "preparing"
                  else "진단 불가 — 모델 또는 기준 정보에 접근할 수 없다")
        raise GateBlocked("G0", "NOT_READY" if state == "preparing" else "UNAVAILABLE", reason, "operator", 503,
                          subject_kind="instance", subject_id=str(runtime.instance_id or 0))


def preload_detector(s: Optional[Settings] = None) -> Dict[str, Any]:
    """관리자: 검출기를 (다시) 적재·웜업. Ollama 면 미리 올리기(가이드 1.6)."""
    s = s or get_settings()
    det = runtime.detector or build_detector(s)
    runtime.detector = det
    t0 = time.perf_counter()
    load_s = det.load()
    check = contract_self_check(det, s)
    runtime.state = DetectorState(kind=det.kind, model=det.model_name, loaded=True, load_seconds=round(load_s, 2),
                                  warmed_up_at=db.now_iso(), last_infer_ms=check.get("infer_ms"), contract_ok=bool(check.get("contract_ok")))
    with db.connect() as conn:
        if runtime.instance_id:
            ops_repo.update_instance(conn, runtime.instance_id, {
                "warmup_done_at": db.now_iso(), "contract_ok": 1 if runtime.state.contract_ok else 0,
                "readiness": "ready" if runtime.state.contract_ok else "unavailable", "readiness_updated_at": db.now_iso(),
                "load_seconds": round(time.perf_counter() - t0, 2),
            })
    return {"kind": det.kind, "model": det.model_name, "action": "preload", "seconds": round(time.perf_counter() - t0, 2),
            "done_reason": "load"}


# ---- P0 상시 루프 ----
async def ops_loop(s: Optional[Settings] = None) -> None:
    s = s or get_settings()
    while runtime.instance_id is None:          # startup(DDL 적용) 이 끝날 때까지 대기
        await asyncio.sleep(1)
    while True:
        try:
            tick(s)
        except Exception as e:  # noqa: BLE001
            log.warning("ops tick failed: %s", e)
        await asyncio.sleep(s.OPS_LOOP_SECONDS)


def tick(s: Optional[Settings] = None) -> Dict[str, Any]:
    """P0 0.4 시연 자동 해제 · 0.5 준비 감시 · 0.2 지표 · 보존. 한 번 실행."""
    s = s or get_settings()
    out: Dict[str, Any] = {}
    now = db.now_iso()
    with db.connect() as conn:
        v = policy_repo.current_validity(conn)
        if v and v["demo_on"] == 1 and v["demo_end_at"] and db.iso(v["demo_end_at"]) <= now:
            policy_repo.supersede_validity(conn, now)
            exc = policy_repo.route_exceptions(conn, v["policy_id"])
            policy_repo.insert_validity(conn, {
                "basis": "headway", "factor": v["factor"], "cap_minutes": v["cap_minutes"], "default_minutes": v["default_minutes"],
                "window_minutes": v["window_minutes"], "demo_on": 0, "demo_end_at": None, "effective_from": now, "created_at": now,
                "created_by": "system:auto-release",
            }, exc)
            out["demo_auto_released"] = True
        # 0.5 준비 감시: 검출기 객체가 사라졌거나 DB 접근 실패 → unavailable
        if runtime.instance_id:
            healthy = runtime.detector is not None and runtime.detector.is_loaded() and runtime.state.contract_ok
            cur = ops_repo.readiness(conn)
            if cur and cur["readiness"] == "ready" and not healthy:
                ops_repo.update_instance(conn, runtime.instance_id, {"readiness": "unavailable", "readiness_updated_at": now})
                out["readiness"] = "unavailable"
        # 0.2 지표: 직전 1시간 결과의 시간대·조도별 신뢰도 편차 (test_call 제외)
        rows = db.q(conn,
            "SELECT a.mean_confidence, a.processed_at, "
            "CASE WHEN EXISTS (SELECT 1 FROM assessment_warning w WHERE w.assessment_id=a.assessment_id AND w.warning_code='low_light') THEN 'low_light' "
            "     WHEN EXISTS (SELECT 1 FROM assessment_warning w WHERE w.assessment_id=a.assessment_id AND w.warning_code='backlight') THEN 'backlight' "
            "     ELSE 'normal' END AS cond "
            "FROM assessment a JOIN diagnosis_request q ON q.request_id=a.request_id "
            "WHERE q.kind <> 'test_call' AND a.processed_at >= :since", since=(datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"))
        if rows:
            overall = sum(r["mean_confidence"] for r in rows) / len(rows)
            groups: Dict[str, list] = {}
            for r in rows:
                groups.setdefault(r["cond"], []).append(r["mean_confidence"])
            hour = datetime.now(timezone.utc).hour
            for cond, vals in groups.items():
                ops_repo.insert_quality_metric(conn, {
                    "hour_of_day": hour, "light_condition": cond, "sample_count": len(vals),
                    "confidence_dev": round(sum(vals) / len(vals) - overall, 4), "out_of_band": None, "computed_at": now,
                })
            out["metrics"] = len(groups)
        # 보존 (R17): 값이 있을 때만
        if s.RETENTION_DAYS:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=s.RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
            n = conn.exec_driver_sql(
                "DELETE FROM assessment_warning WHERE assessment_id IN (SELECT assessment_id FROM assessment WHERE processed_at < ?)", (cutoff,)
            ).rowcount
            out["retention_deleted_warnings"] = n
    return out
