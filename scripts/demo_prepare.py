"""시연 준비 스크립트 (T052) — HG/시연웹/01-시연-시나리오.md §3 P1~P6 을 한 번에 실행한다.

P1 준비 상태 확인 → P2 카메라 3대 → P3 ROI(화면 전체)·정원·카메라 전원 켜기 → P4 매핑(지금 도착 예정인 차량 순, `/v1/admin/demo/bis-remap`)
→ P5 시연 모드 켜기 → P6 프레임 3장 일괄 등록 → 장면 1 (S7 조회) 응답 출력.

노선·정류장 기본값은 실제 BIS 시연(102번 30300037 · 충남대학교 (홈플러스유성점 방면)). BIS 장애로 EXTERNAL_PROVIDER=fixture 로
되돌려도 같은 노선·정류장의 예비 데이터가 있어 그대로 돈다(quickstart §6-1). 옛 고정 시연은 --route R102 --stop 3001.

프레임 (T054 대체, 2026-09-29 사용자 결정 ④): 샘플 영상(backend/samples/videos, 출처·라이선스는 samples/README.md)에서 한 장씩 뽑는다.
  혼잡 = 역 대합실 인파, 여유 = 열차 차내, 흐림 = 대합실 프레임에 가우시안 블러(판독 불확실 시연).
  R22(인원 ÷ 정원)에서는 도형 합성 그림이 0명으로 세어지므로, 영상이 없을 때만 합성 그림으로 대신한다.

사용: python scripts/demo_prepare.py [--route 30300037] [--stop 30300037:42620] [--base …] [--web-base …] [--samples backend/samples] [--reset]
  --reset: 서버를 내리고 cv.db 를 지운 뒤 다시 기동하라는 안내를 출력한다 (프로세스는 건드리지 않는다).
"""
from __future__ import annotations

import argparse
import os
import io
import sys
import time
from pathlib import Path

import httpx
from _split_client import API_BASE, WEB_BASE, SplitClient, env_keys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
# (카메라, 샘플 영상, 뽑을 위치 0~1, 블러) — 사진 파일(bus_*.jpg)이 samples/ 에 있으면 그것을 먼저 쓴다
# 위치는 YOLOv8n·입력 1280·인원 세기 기준 0.4 로 10구간을 훑어 가장 많이 잡히는 곳(2026-09-29): 대합실 45% = 16명, 차내 55% = 1명.
# 밀집 과소 계수(research R22 한계)로 대합실도 16명뿐이라 정원 80명 차량에서는 "여유"로 나온다.
CAMS = [("CAM-DEMO-01", "videos/concourse_crowded_saint_lazare.webm", 0.45, False, "bus_full.jpg"),
        ("CAM-DEMO-02", "videos/train_interior_nyc.webm", 0.55, False, "bus_empty.jpg"),
        ("CAM-DEMO-03", "videos/concourse_crowded_saint_lazare.webm", 0.45, True, "bus_blur.jpg")]   # 사람이 있어도 흐리면 판독 불확실
ROI = {"polygon": [[0, 0], [4096, 0], [4096, 4096], [0, 4096]], "effective_from": "2026-01-01T00:00:00"}   # 화면 전체 (R22 — ROI 는 셀 사람만 거른다)


def synth(persons: int, blur: bool = False) -> bytes:
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), (172, 172, 176)); d = ImageDraw.Draw(img)
    d.rectangle([80, 300, w - 80, h - 40], fill=(118, 118, 124))
    for i in range(persons):
        x = 120 + (i % 14) * 78; y = 250 + (i // 14) * 40
        d.rectangle([x, y, x + 60, y + 360], fill=(35, 35, 55)); d.ellipse([x + 8, y - 55, x + 52, y - 5], fill=(205, 175, 155))
    arr = np.asarray(img).astype("int16") + np.random.default_rng(3).integers(-26, 26, size=(h, w, 1), dtype="int16")
    img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(9))
    b = io.BytesIO(); img.save(b, "JPEG", quality=88); return b.getvalue()


def video_frame(path: Path, at: float) -> Image.Image | None:
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(str(path))
    try:
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * at))
        ok, bgr = cap.read()
    finally:
        cap.release()
    return Image.fromarray(bgr[:, :, ::-1]) if ok else None


def frame_bytes(samples: Path, video: str, at: float, blur: bool, photo: str, persons: int) -> tuple[bytes, str]:
    """(JPEG, 출처 설명). 사진 → 영상 프레임 → 합성 그림 순."""
    src = samples / photo
    if src.exists():
        im, how = Image.open(src).convert("RGB"), photo
    else:
        im = video_frame(samples / video, at)
        how = f"{video} @{at:.0%}"
        if im is None:
            return synth(persons, blur), "합성 그림 (영상 없음 — R22 에서는 0명으로 세어진다)"
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(9)); how += " + 블러"
    b = io.BytesIO(); im.save(b, "JPEG", quality=90); return b.getvalue(), how


class Gate(Exception):
    pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=API_BASE); ap.add_argument("--web-base", default=WEB_BASE)
    ap.add_argument("--samples", default=str(ROOT / "backend" / "samples")); ap.add_argument("--reset", action="store_true")
    ap.add_argument("--route", default="30300037", help="102번 BIS ROUTE_CD (옛 고정 시연은 R102)")
    ap.add_argument("--stop", default="30300037:42620", help="충남대학교 (홈플러스유성점 방면) (옛 고정 시연은 3001)")
    a = ap.parse_args()
    if a.reset:
        print("--reset: 서버를 내리고 `rm backend/cv.db` 후 백엔드(`cd backend && python -m cv_api.serve`)를 재기동한 다음 이 스크립트를 다시 실행한다.")
        return 0
    key, admin = env_keys()   # 키는 환경변수·키 파일에서만 (D8)
    K = {"X-API-Key": key}; A = {"X-Admin-Key": admin}
    c = SplitClient(a.base, a.web_base, timeout=120)
    samples = Path(a.samples)

    def call(step: str, r: httpx.Response, ok=(200, 201)) -> dict:
        j = r.json() if r.content else {}
        if r.status_code in ok or (r.status_code == 422 and str(j.get("reason_code", "")).endswith(("EXISTS", "DUPLICATE_VERSION", "ALREADY_MAPPED"))):
            print(f"  OK  {step}"); return j
        raise Gate(f"{step} → HTTP {r.status_code} {j.get('gate', '')} {j.get('reason_code', '')}: {j.get('reason') or j}")

    try:
        print("P1 준비 상태")
        for _ in range(30):
            r = c.get("/v1/readiness").json()
            if r["readiness"] == "ready": break
            print(f"  … {r['readiness']} ({(r.get('detector') or {}).get('note')})"); time.sleep(2)
        else:
            raise Gate("G0 준비 상태가 ready 가 되지 않았다")
        print(f"  OK  ready — 검출기 {r['detector']['kind']} 적재 {r['detector']['load_seconds']}s")
        src = c.get("/v1/admin/ops-status", headers=A).json()
        print(f"      운행 정보: 노선 {a.route} · 정류장 {a.stop} · BIS 호출 오늘 {src.get('bis_calls_today', '?')}회")
        print("P2 카메라 등록")
        for cam, *_ in CAMS:
            call(cam, c.post("/v1/admin/cameras", headers=A, json={"camera_id": cam, "place_type": "bus_in", "route_id": a.route, "vehicle_type_id": "VT_LOW"}))
        print("P3 ROI(화면 전체) · 정원 · 카메라 전원")
        for cam, *_ in CAMS:
            call(f"ROI {cam}", c.post(f"/v1/admin/cameras/{cam}/roi", headers=A, json=ROI))
        call("정원 VT_LOW 80/30", c.post("/v1/admin/vehicle-types/VT_LOW/spec", headers=A, json={"capacity": 80, "seat_count": 30, "source": "제조사 제원표", "effective_from": "2026-01-01T00:00:00"}))
        # 카메라는 꺼진 채로 등록된다(S2b) — 꺼져 있으면 P6 진단이 반려된다. 프레임 소스가 없으므로 켜도 자동 진단은 돌지 않는다
        for cam, *_ in CAMS:
            call(f"전원 켜기 {cam}", c.post(f"/v1/admin/cameras/{cam}/power", headers=A, json={"on": True}))
        print("P4 매핑 — 지금 도착 예정인 차량 순으로 다시 연결 (S8 8.1 과 같다)")
        rm = call("demo/bis-remap", c.post("/v1/admin/demo/bis-remap", headers=A, json={"route_id": a.route, "stop_id": a.stop, "camera_ids": [x[0] for x in CAMS]}))
        for row in rm.get("rows", []):
            print(f"      {row['camera_id']}  {row.get('before') or '—'} → {row.get('after') or '—'}  {row.get('action')}  도착 {row.get('expected_arrival_at') or '—'}")
        veh_of = {m["camera_id"]: m["vehicle_id"] for m in c.get("/v1/admin/mappings", headers=A).json()}
        missing = [cam for cam, *_ in CAMS if cam not in veh_of]
        if missing:
            raise Gate(f"G12 도착 예정 차량이 모자라 {missing} 에 연결할 차량이 없다 ({rm.get('message')}) — 첫차 전·막차 후면 fixture 예비 절차(quickstart §6-1)")
        print("P5 시연 모드 켜기 (기본 +2시간)")
        v = call("validity demo_on", c.post("/v1/admin/policies/validity", headers=A, json={"factor": 1.0, "cap_minutes": 30, "demo_on": True}))
        print(f"      종료 예정 {v['policy'].get('demo_end_at')}")
        print("P6 사전 촬영 프레임 일괄 등록")
        files, data = [], {"seq": [], "vehicle_id": [], "camera_id": []}
        for i, (cam, video, at, blur, photo) in enumerate(CAMS, start=1):
            jpg, how = frame_bytes(samples, video, at, blur, photo, persons=(18, 3, 10)[i - 1])
            print(f"      seq {i} {cam} ← {how}")
            files.append(("frame", (f"{cam}.jpg", jpg, "image/jpeg")))
            data["seq"].append(str(i)); data["vehicle_id"].append(veh_of[cam]); data["camera_id"].append(cam)
        j = call("measurements/batch", c.post("/v1/measurements/batch", headers=A, data=data, files=files))
        for it in j["items"]:
            m = (it.get("result") or {}).get("measurement") or {}
            ass = (it.get("result") or {}).get("assessment") or {}
            print(f"      seq {it['seq']} {it['vehicle_id']} {it['status']} → 인원 {ass.get('person_count')} · 잔여 {m.get('vacant_ratio_agg')}% {m.get('crowding_level_agg')} demo={m.get('demo_mode')} {(it.get('reject') or {}).get('reason', '')}")
        print(f"장면 1 — S7 후속 차량 조회 ({a.route} / {a.stop})")
        nv = call("next-vehicle", c.get("/v1/next-vehicle", headers=K, params={"route_id": a.route, "stop_id": a.stop, "limit": 4}))
        for veh in nv["vehicles"]:
            print(f"      {veh['vehicle_id']}  {veh['basis_type']:15s} {veh.get('vacant_ratio')}  {veh.get('crowding_level')}  cov {veh.get('coverage_num')}/{veh.get('coverage_den')}")
        print(f"      demo_mode={nv['demo_mode']} 유효 시간 {nv['applied_validity_minutes']}분")
        print(f"      운행 정보 {nv['source_status']} · BIS 호출 오늘 {c.get('/v1/admin/ops-status', headers=A).json().get('bis_calls_today', '?')}회")
        print(f"\nPASS — 웹 S7 (http://<서버IP>:9504/next-vehicle?route_id={a.route}&stop_id={a.stop}) 에서 같은 표가 보인다. 발표 후 S8 8.5 로 시연 모드를 끈다.")
        return 0
    except Gate as g:
        print(f"\nFAIL {g}\n  게이트 사유를 해결한 뒤 다시 실행한다 (SD_02 §14 참조)."); return 1


if __name__ == "__main__":
    sys.exit(main())
