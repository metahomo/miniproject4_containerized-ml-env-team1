"""웹 화면용 제출 경로 — 규격 밖 사진·영상을 규격에 맞춰 진단 API(9544)에 넘긴다. 웹 백엔드(9524)가 서빙한다.

- 연계 시스템은 쓰지 않는다(카탈로그 밖). 진단 API 의 계약(규격 밖 반려, BR-CV-11)은 그대로다.
- 호출 키는 받은 그대로 진단 API 에 전달한다 — 집계 기록의 caller_id 가 원래 호출자로 남는다.
- 응답은 진단 API 응답 + `normalization`(무엇을 바꿨는지). 진단 API 가 반려하면 그 상태·본문을 그대로 돌려준다.
- 샘플(`/v1/web/samples`): 서버에 미리 둔 자유 이용 허가 사진·영상(`backend/samples/catalog.json`)을 내준다. 화면은 받은 파일을
  로컬 파일과 똑같이 제출한다 — 이용자 원본이 아니므로 FR-11 대상이 아니다. 카탈로그에 없는 경로는 404.
"""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .. import media
from ..auth import require_caller
from ..gates import GateBlocked
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1/web", tags=["web"], dependencies=[Depends(require_caller)])

# 이 게이트로 막히면 영상의 나머지 프레임도 같은 결과라 멈춘다 (준비·인증·카메라·ROI·모델)
_ABORT_GATES = {"G0", "G1", "G3", "G4", "G5"}


_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}
mimetypes.add_type("video/webm", ".webm")


def _samples(s: Settings) -> List[Dict[str, Any]]:
    """catalog.json 항목 중 파일이 실제로 있는 것만. 카탈로그가 없거나 깨졌으면 빈 목록."""
    try:
        entries = json.loads((s.SAMPLES_DIR / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    root = s.SAMPLES_DIR.resolve()
    out = []
    for e in entries if isinstance(entries, list) else []:
        path = (root / str(e.get("file", ""))).resolve()
        if root not in path.parents or not path.is_file():
            continue
        out.append({**e, "kind": "video" if path.suffix.lower() in _VIDEO_EXT else "image", "bytes": path.stat().st_size,
                    "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream", "_path": path})
    return out


@router.get("/samples", summary="샘플 사진·영상 목록 — 서버에 미리 둔 자유 이용 허가 자료 (웹 화면용)")
def list_samples(s: Settings = Depends(get_settings)) -> List[Dict[str, Any]]:
    return [{k: v for k, v in e.items() if k != "_path"} for e in _samples(s)]


@router.get("/samples/{file:path}", summary="샘플 파일 내려받기 — 카탈로그에 있는 파일만")
def get_sample(file: str, s: Settings = Depends(get_settings)) -> FileResponse:
    e = next((e for e in _samples(s) if e["file"] == file), None)
    if e is None:
        raise HTTPException(404, f"샘플이 없다: {file}")
    return FileResponse(e["_path"], media_type=e["content_type"], filename=e["_path"].name)


def _api_client(s: Settings) -> httpx.Client:
    """진단 API 클라이언트. 테스트는 이 함수를 진단 API 앱의 TestClient 로 바꾼다."""
    return httpx.Client(base_url=s.DIAGNOSIS_API_URL, timeout=max(30.0, s.OLLAMA_INFER_TIMEOUT_S))


def _keys(request: Request) -> Dict[str, str]:
    return {k: v for k in ("X-API-Key", "X-Admin-Key", "Authorization") if (v := request.headers.get(k))}   # 로그인 토큰도 그대로 (RBAC)


def _relay(s: Settings, request: Request, path: str, form: Dict[str, str], jpeg: bytes) -> httpx.Response:
    if not s.DIAGNOSIS_API_URL:
        raise GateBlocked("G0", "API_URL_MISSING", "진단 API 주소(DIAGNOSIS_API_URL)가 설정되지 않았다 — .env 에 지정 모델 게이트웨이를 둔다",
                          "operator", 503, record=False)
    try:
        with _api_client(s) as c:
            return c.post(path, headers=_keys(request), data={k: v for k, v in form.items() if v},
                          files={"frame": ("frame.jpg", jpeg, "image/jpeg")})
    except httpx.TransportError as e:
        raise GateBlocked("G0", "API_UNREACHABLE", f"진단 API 서버에 연결할 수 없다 ({s.DIAGNOSIS_API_URL})", "operator", 503,
                          record=False) from e


def _json(r: httpx.Response) -> Dict[str, Any]:
    try:
        j = r.json()
        return j if isinstance(j, dict) else {"detail": j}
    except ValueError:
        return {"detail": r.text[:300]}


def _shift(started_at: Optional[str], t: float) -> Optional[str]:
    if not started_at:
        return None
    try:
        base = datetime.fromisoformat(started_at.replace("Z", ""))
    except ValueError:
        raise GateBlocked("G2", "INVALID_STARTED_AT", f"영상 시작 시각 형식 오류: {started_at} (예: 2026-09-29T08:30:00)", "self", 422,
                          record=False) from None
    return (base + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%S")


@router.post("/diagnose", summary="사진 진단 — 규격 밖이면 변환 후 진단 API 로 (웹 화면용)")
def diagnose_image(request: Request, camera_id: str = Form(...), file: UploadFile = File(...), captured_at: Optional[str] = Form(default=None),
                   s: Settings = Depends(get_settings)) -> JSONResponse:
    jpeg, norm = media.normalize_image(file.file.read(), s)
    r = _relay(s, request, "/v1/diagnose", {"camera_id": camera_id, "captured_at": captured_at or ""}, jpeg)
    del jpeg
    return JSONResponse(status_code=r.status_code, content={**_json(r), "normalization": norm.as_dict()})


@router.post("/measurements", summary="후속 차량 실측 — 규격 밖 사진이면 변환 후 진단 API 로 (웹 화면용)")
def measurement_image(request: Request, vehicle_id: str = Form(...), camera_id: str = Form(...), file: UploadFile = File(...),
                      captured_at: Optional[str] = Form(default=None), s: Settings = Depends(get_settings)) -> JSONResponse:
    jpeg, norm = media.normalize_image(file.file.read(), s)
    r = _relay(s, request, "/v1/measurements", {"vehicle_id": vehicle_id, "camera_id": camera_id, "captured_at": captured_at or ""}, jpeg)
    del jpeg
    return JSONResponse(status_code=r.status_code, content={**_json(r), "normalization": norm.as_dict()})


@router.post("/diagnose-video", summary="영상 진단 — 간격마다(또는 at_s 한 장) 프레임을 뽑아 진단, 추이·평활값 (웹 화면용)")
def diagnose_video(request: Request, camera_id: str = Form(...), file: UploadFile = File(...),
                   interval_s: Optional[float] = Form(default=None), at_s: Optional[float] = Form(default=None),
                   started_at: Optional[str] = Form(default=None), s: Settings = Depends(get_settings)) -> JSONResponse:
    data = file.file.read()
    items: List[Dict[str, Any]] = []
    with media.open_video(data, file.filename or "", s) as (cap, info):
        del data
        times, step = media.sample_times(info, interval_s, at_s, s)
        for t in times:
            frame = media.read_frame(cap, t)
            if frame is None:
                items.append({"t": t, "status": "rejected", "reject": {"gate": "G2", "reason_code": "FRAME_READ_FAILED",
                                                                      "reason": f"{t}초 프레임을 읽지 못했다"}})
                continue
            try:
                jpeg, norm = media.normalize_frame(frame, s)
            except GateBlocked as g:
                items.append({"t": t, "status": "rejected", "reject": g.to_dict()})
                continue
            r = _relay(s, request, "/v1/diagnose", {"camera_id": camera_id, "captured_at": _shift(started_at, t) or ""}, jpeg)
            body = _json(r)
            if r.status_code == 200:
                items.append({"t": t, "status": "accepted", "assessment": body})
            elif body.get("gate") in _ABORT_GATES:
                return JSONResponse(status_code=r.status_code, content={**body, "video": info.__dict__, "stopped_at_s": t})
            else:
                items.append({"t": t, "status": "rejected", "reject": body})
    vac = [it["assessment"]["vacant_capacity_ratio"] if it["status"] == "accepted" else None for it in items]
    smooth = media.rolling_median(vac, s.VIDEO_SMOOTH_WINDOW)
    for it, sm in zip(items, smooth):
        it["smoothed_vacant_ratio"] = sm
    got = [v for v in vac if v is not None]
    uncertain = sum(1 for it in items if it["status"] == "accepted" and it["assessment"].get("is_reference_only"))
    return JSONResponse(content={
        "camera_id": camera_id, "video": info.__dict__, "interval_s": step, "requested_interval_s": interval_s, "mode": "single" if at_s is not None else "interval",
        "items": items,
        "summary": {"frames": len(items), "accepted": len(got), "uncertain": uncertain, "rejected": len(items) - len(got),
                    "vacant_min": min(got) if got else None, "vacant_max": max(got) if got else None,
                    "vacant_median": media.rolling_median(got, len(got))[-1] if got else None},
        "smooth_window": s.VIDEO_SMOOTH_WINDOW,
        "normalization": {"steps": [f"영상 {info.width}×{info.height} {info.codec} {info.duration_s}초", f"{len(items)}장 추출"],
                          "max_side": s.NORMALIZE_MAX_SIDE},
    })
