"""카메라 전원 관리 (S2b «카메라 전원 관리», 2026-09-29 사용자 결정).

- off(기본): 그 카메라의 진단 요청을 거부한다 — diagnosis._reference 의 G4 CAMERA_POWER_OFF (409).
- on: 서버가 카메라마다 poll_interval_s 초마다 frame_source 에서 프레임 1장을 불러와 진단한다(P5 와 같은 함수).
  frame_source = 스냅샷 URL(http/https, JPEG·PNG 등 → 규격 JPEG 로 변환) 또는 `sample:<샘플 파일>`(backend/samples 카탈로그).
  샘플 영상은 켠 시각부터 흐른 시간만큼 반복 재생한 위치의 프레임을 쓴다(실제 카메라처럼 장면이 바뀐다).
  프레임은 진단 후 버리고 저장하지 않는다(FR-11). 소스가 없으면 자동 진단은 하지 않고 요청만 받는다(노트북 카메라 등).
- 표(overview): 호선·차량번호·칸·운행 상태·정원·현재 인원·밀집도·동작여부(정상/오프라인/꺼짐).
  동작여부: 꺼짐 = off, 정상 = on 이고 최근 ONLINE_WINDOW_S 안에 진단 기록, 오프라인 = 그 밖.
  운행 상태: 매핑된 차량이 최근 RUN_WINDOW_S 안의 BIS 도착 정보에 있으면 운행중, 없으면 정차, 매핑이 없으면 None.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import cv2
import httpx

from .. import db, media
from ..gates import GateBlocked, resolve_gate_events
from ..settings import Settings, get_settings

log = logging.getLogger("cv_api.camera_power")

ONLINE_WINDOW_S = 300        # 동작여부 «정상» 판단 창 (5분)
RUN_WINDOW_S = 600           # 운행 상태 «운행중» 판단 창 (BIS 도착 정보 10분)
SCHEDULER_CALLER = "scheduler"
SAMPLE_PREFIX = "sample:"


class PollState:
    """프로세스 메모리의 카메라별 자동 진단 상태 (표의 «마지막 오류» 표시용). DB 에 남기지 않는다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_poll: Dict[str, float] = {}
        self.last_error: Dict[str, Optional[str]] = {}
        self.started: Dict[str, float] = {}

    def forget(self, camera_id: str) -> None:
        with self._lock:
            self.last_poll.pop(camera_id, None)
            self.last_error.pop(camera_id, None)
            self.started.pop(camera_id, None)

    def mark(self, camera_id: str, error: Optional[str]) -> None:
        with self._lock:
            self.last_poll[camera_id] = time.monotonic()
            self.last_error[camera_id] = error


state = PollState()


# ------------------------------------------------------------------ 조회
def _camera(conn, camera_id: str) -> Dict[str, Any]:
    row = db.q1(conn, "SELECT * FROM camera WHERE camera_id=:c", c=camera_id)
    if not row:
        raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404, subject_kind="camera", subject_id=camera_id)
    return row


def _mode(place_type: str, route_mode: Optional[str]) -> str:
    if place_type == "train_in":
        return "rail"
    if place_type == "bus_in":
        return "bus"
    return route_mode or "bus"


def _ago(ts: Optional[str], now: datetime) -> Optional[float]:
    if not ts:
        return None
    try:
        return (now - datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds()
    except ValueError:
        return None


def overview() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    since_run = (now - timedelta(seconds=RUN_WINDOW_S)).strftime("%Y-%m-%dT%H:%M:%S")
    with db.connect() as conn:
        cams = db.q(conn,
                    "SELECT c.*, r.route_name, r.mode AS route_mode, v.vehicle_id, s.capacity "
                    "FROM camera c LEFT JOIN route r ON r.route_id = c.route_id "
                    "LEFT JOIN v_camera_readiness v ON v.camera_id = c.camera_id "
                    "LEFT JOIN vehicle_spec s ON s.spec_id = v.spec_id ORDER BY c.camera_id")
        latest = {r["camera_id"]: r for r in db.q(conn,
                  "SELECT q.camera_id, a.person_count, a.occupied_area_ratio, a.crowding_level, a.processed_at "
                  "FROM assessment a JOIN diagnosis_request q ON q.request_id = a.request_id "
                  "WHERE a.assessment_id IN (SELECT MAX(a2.assessment_id) FROM assessment a2 "
                  "JOIN diagnosis_request q2 ON q2.request_id = a2.request_id GROUP BY q2.camera_id)")}
        running = {r["vehicle_id"] for r in db.q(conn,
                   "SELECT DISTINCT vehicle_id FROM arrival_snapshot WHERE source_status='ok' AND vehicle_id IS NOT NULL AND fetched_at >= :t",
                   t=since_run)}
    out = []
    for c in cams:
        a = latest.get(c["camera_id"])
        age = _ago(a["processed_at"], now) if a else None
        powered = bool(c.get("powered"))
        operation = "off" if not powered else ("normal" if age is not None and age <= ONLINE_WINDOW_S else "offline")
        persons = a["person_count"] if a else None
        cap = c.get("capacity")
        density = round(100.0 * persons / cap, 1) if persons is not None and cap else None   # 정원 없으면 산출 불가 (G7)
        vid = c.get("vehicle_id")
        out.append({
            "camera_id": c["camera_id"], "mode": _mode(c["place_type"], c.get("route_mode")), "place_type": c["place_type"],
            "route_id": c.get("route_id"), "route_name": c.get("route_name"), "vehicle_id": vid,
            "car_position": c.get("car_position"),
            "run_state": None if not vid else ("running" if vid in running else "stopped"),
            "capacity": cap, "persons": persons, "density": density, "crowding_level": a["crowding_level"] if a else None,
            "last_diagnosed_at": a["processed_at"] if a else None,
            "powered": powered, "powered_at": c.get("powered_at"), "operation": operation,
            "frame_source": c.get("frame_source"), "poll_interval_s": float(c.get("poll_interval_s") or 10),
            "last_error": state.last_error.get(c["camera_id"]) if powered else None,
        })
    return out


def overview_row(camera_id: str) -> Dict[str, Any]:
    return next(r for r in overview() if r["camera_id"] == camera_id)


# ------------------------------------------------------------------ 변경
def set_power(camera_id: str, on: bool, by: str) -> Dict[str, Any]:
    with db.connect() as conn:
        _camera(conn, camera_id)
        db.update(conn, "camera", "camera_id=:c", {"powered": 1 if on else 0, "powered_at": db.now_iso()}, c=camera_id)
        if on:
            resolve_gate_events(conn, "G4", "camera", camera_id, by, "camera:powered_on")
    state.forget(camera_id)   # 켜면 바로 한 장, 끄면 오류 표시도 지운다
    return overview_row(camera_id)


def update_settings(camera_id: str, body: Dict[str, Any], s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    with db.connect() as conn:
        _camera(conn, camera_id)
        fields: Dict[str, Any] = {}
        if "car_position" in body:
            fields["car_position"] = body["car_position"]
        if "frame_source" in body:
            src = (body["frame_source"] or "").strip() or None
            if src:
                _check_source(src, s)
            fields["frame_source"] = src
        if "poll_interval_s" in body and body["poll_interval_s"] is not None:
            fields["poll_interval_s"] = float(body["poll_interval_s"])
        if fields:
            db.update(conn, "camera", "camera_id=:c", fields, c=camera_id)
    state.forget(camera_id)
    return overview_row(camera_id)


def _check_source(src: str, s: Settings) -> None:
    def bad(why: str) -> GateBlocked:
        return GateBlocked("G8", "FRAME_SOURCE_INVALID", f"프레임 소스 — {why}", "self", 422, record=False)
    if src.startswith(SAMPLE_PREFIX):
        if _sample_path(src[len(SAMPLE_PREFIX):], s) is None:
            raise bad(f"샘플 카탈로그에 없는 파일: {src[len(SAMPLE_PREFIX):]}")
    elif not src.startswith(("http://", "https://")):
        raise bad("http(s):// 스냅샷 주소 또는 sample:<샘플 파일> 이어야 한다")


def _sample_path(name: str, s: Settings):
    try:
        entries = json.loads((s.SAMPLES_DIR / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not any(isinstance(e, dict) and e.get("file") == name for e in entries if isinstance(entries, list)):
        return None
    root = s.SAMPLES_DIR.resolve()
    p = (root / name).resolve()
    return p if root in p.parents and p.is_file() else None


# ------------------------------------------------------------------ 프레임 불러오기
_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}


def fetch_frame(camera_id: str, src: str, s: Settings) -> bytes:
    """소스에서 프레임 1장 → 규격 JPEG. 실패는 RuntimeError(사유)."""
    if src.startswith(SAMPLE_PREFIX):
        path = _sample_path(src[len(SAMPLE_PREFIX):], s)
        if path is None:
            raise RuntimeError("샘플 파일이 없다")
        if path.suffix.lower() in _VIDEO_EXT:
            cap = cv2.VideoCapture(str(path))
            try:
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if not cap.isOpened() or fps <= 0 or n <= 0:
                    raise RuntimeError("샘플 영상을 읽을 수 없다")
                dur = n / fps
                t0 = state.started.setdefault(camera_id, time.monotonic())
                frame = media.read_frame(cap, (time.monotonic() - t0) % max(dur - 1.0 / fps, 0.001))
            finally:
                cap.release()
            if frame is None:
                raise RuntimeError("샘플 영상 프레임을 뽑지 못했다")
            return media.normalize_frame(frame, s)[0]
        return media.normalize_image(path.read_bytes(), s)[0]
    try:
        r = httpx.get(src, timeout=10.0, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise RuntimeError(f"스냅샷을 불러오지 못했다 — {type(e).__name__}") from None
    try:
        return media.normalize_image(r.content, s)[0]
    except GateBlocked as g:
        raise RuntimeError(g.reason) from None


def poll_once(camera_id: str, src: str, s: Optional[Settings] = None) -> Optional[str]:
    """한 장 불러와 진단. 반환: 오류 사유(성공이면 None)."""
    from .diagnosis import diagnose   # 순환 import 회피

    s = s or get_settings()
    try:
        data = fetch_frame(camera_id, src, s)
        diagnose(data, camera_id, SCHEDULER_CALLER, kind="single", captured_at=db.now_iso(), s=s)
        err = None
    except GateBlocked as g:
        err = g.reason
    except Exception as e:  # noqa: BLE001 — 한 카메라의 실패가 스케줄러를 멈추지 않게
        err = str(e) or type(e).__name__
    finally:
        data = None   # FR-11
    state.mark(camera_id, err)
    return err


def due_cameras(now_mono: Optional[float] = None) -> List[Dict[str, Any]]:
    now_mono = time.monotonic() if now_mono is None else now_mono
    with db.connect() as conn:
        rows = db.q(conn, "SELECT camera_id, frame_source, poll_interval_s FROM camera WHERE powered = 1 AND frame_source IS NOT NULL")
    out = []
    for r in rows:
        last = state.last_poll.get(r["camera_id"])
        if last is None or now_mono - last >= float(r["poll_interval_s"] or 10):
            out.append(r)
    return out


async def scheduler_loop(s: Settings, tick_s: float = 1.0) -> None:
    """켜진 카메라를 주기마다 진단. 검출기 1개를 나눠 쓰므로 한 번에 1건씩 순서대로 (Ollama 동시 1건 규칙과도 맞다)."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            for r in await loop.run_in_executor(None, due_cameras):
                await loop.run_in_executor(None, poll_once, r["camera_id"], r["frame_source"], s)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("camera scheduler tick failed: %s", e)
        await asyncio.sleep(tick_s)
