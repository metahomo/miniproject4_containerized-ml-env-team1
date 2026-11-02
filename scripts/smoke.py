"""엔드투엔드 스모크 — 기동된 서버에 대해 P2→P5→P6→P7 을 한 바퀴 돈다. quickstart §2·§3 과 같다.

사용: python scripts/smoke.py [--base http://localhost:9544] [--web-base http://localhost:9524]
"""
from __future__ import annotations

import argparse
import os
import io
import json
import sys

import httpx
from _split_client import API_BASE, WEB_BASE, SplitClient, env_keys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def synth_frame(w=1280, h=720, persons=0, blur=False, dark=False) -> bytes:
    img = Image.new("RGB", (w, h), (170, 170, 175))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 300, w - 80, h - 40], fill=(120, 120, 125))          # 바닥
    for i in range(persons):
        x = 200 + i * 140
        d.rectangle([x, 260, x + 70, 620], fill=(40, 40, 60))            # 몸
        d.ellipse([x + 10, 200, x + 60, 260], fill=(200, 170, 150))      # 머리
    rng = np.random.default_rng(7)
    arr = np.asarray(img).astype("int16") + rng.integers(-28, 28, size=(h, w, 1), dtype="int16")   # 질감 (실사 근사)
    img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(9))
    if dark:
        img = Image.fromarray((np.asarray(img) * 0.12).astype("uint8"))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=88); return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default=API_BASE); ap.add_argument("--web-base", default=WEB_BASE)
    a = ap.parse_args()
    key, admin = env_keys()   # 키는 환경변수·키 파일에서만 (D8)
    K = {"X-API-Key": key}; A = {"X-Admin-Key": admin}
    c = SplitClient(a.base, a.web_base, timeout=60)
    ok = True

    def step(name, r, expect):
        nonlocal ok
        good = r.status_code in expect
        ok &= good
        body = r.text[:160].replace("\n", " ")
        print(f"{'OK ' if good else 'NG '} {name:38s} {r.status_code} {body}")
        return r

    step("readiness", c.get("/v1/readiness"), {200})
    # 기준 정보 (fixture 노선 R102 / 정류장 3001 은 load_reference 로 적재되어 있어야 함)
    step("camera CAM-DEMO-01", c.post("/v1/admin/cameras", headers=A, json={"camera_id": "CAM-DEMO-01", "place_type": "bus_in", "route_id": "R102", "vehicle_type_id": "VT_LOW"}), {201, 422})
    step("camera CAM-DEMO-02", c.post("/v1/admin/cameras", headers=A, json={"camera_id": "CAM-DEMO-02", "place_type": "bus_in", "route_id": "R102", "vehicle_type_id": "VT_LOW"}), {201, 422})
    step("camera CAM-S03 (platform)", c.post("/v1/admin/cameras", headers=A, json={"camera_id": "CAM-S03", "place_type": "platform", "route_id": "R102", "stop_id": "3001"}), {201, 422})
    step("diagnose without ROI → 409 G4", c.post("/v1/diagnose", headers=K, data={"camera_id": "CAM-DEMO-01"}, files={"frame": ("f.jpg", synth_frame(), "image/jpeg")}), {409})
    roi = {"polygon": [[80, 300], [1200, 300], [1200, 680], [80, 680]], "roi_area_m2": 6.5, "effective_from": "2026-01-01T00:00:00"}
    step("roi CAM-DEMO-01", c.post("/v1/admin/cameras/CAM-DEMO-01/roi", headers=A, json=roi), {201})
    step("roi CAM-DEMO-02", c.post("/v1/admin/cameras/CAM-DEMO-02/roi", headers=A, json=roi), {201})
    step("roi invalid (2 pts) → 422 G8", c.post("/v1/admin/cameras/CAM-DEMO-01/roi", headers=A, json={"polygon": [[0, 0], [1, 1]], "effective_from": "2026-01-01T00:00:00"}), {422})
    step("spec VT_LOW", c.post("/v1/admin/vehicle-types/VT_LOW/spec", headers=A, json={"capacity": 80, "seat_count": 30, "source": "제조사 제원표", "effective_from": "2026-01-01T00:00:00"}), {201})
    step("spec seat>cap → 422 G8", c.post("/v1/admin/vehicle-types/VT_LOW/spec", headers=A, json={"capacity": 40, "seat_count": 50, "source": "x", "effective_from": "2026-01-01T00:00:00"}), {422})
    step("mapping 1234←CAM-DEMO-01", c.post("/v1/admin/mappings", headers=A, json={"camera_id": "CAM-DEMO-01", "vehicle_id": "1234", "vehicle_type_id": "VT_LOW"}), {201, 422})
    step("mapping 1234←CAM-DEMO-02", c.post("/v1/admin/mappings", headers=A, json={"camera_id": "CAM-DEMO-02", "vehicle_id": "1234", "vehicle_type_id": "VT_LOW"}), {201, 422})
    step("mapping 9999 not in fleet → 422 G9", c.post("/v1/admin/mappings", headers=A, json={"camera_id": "CAM-S03", "vehicle_id": "9999"}), {422})
    step("threshold past date → 422 G8", c.post("/v1/admin/policies/threshold", headers=A, json={"free_min_ratio": 50, "crowded_max_ratio": 20, "effective_from": "2020-01-01T00:00:00"}), {422})
    step("validity view", c.get("/v1/admin/policies/validity", headers=A), {200})
    # 진단
    r = step("diagnose normal", c.post("/v1/diagnose", headers=K, data={"camera_id": "CAM-DEMO-01", "captured_at": "2026-09-28T09:41:00"}, files={"frame": ("f.jpg", synth_frame(persons=2), "image/jpeg")}), {200})
    if r.status_code == 200:
        j = r.json(); print("     →", {k: j[k] for k in ("vacant_capacity_ratio", "crowding_level", "person_count", "remaining_persons", "mean_confidence", "response_ms")}, [w["code"] for w in j["warnings"]])
    r = step("diagnose blur → uncertain", c.post("/v1/diagnose", headers=K, data={"camera_id": "CAM-DEMO-01"}, files={"frame": ("f.jpg", synth_frame(persons=2, blur=True), "image/jpeg")}), {200})
    if r.status_code == 200:
        j = r.json(); print("     →", j["crowding_level"], j["is_reference_only"], [w["code"] for w in j["warnings"]])
        ok &= j["crowding_level"] == "uncertain"
    step("diagnose bmp → 422 G2", c.post("/v1/diagnose", headers=K, data={"camera_id": "CAM-DEMO-01"}, files={"frame": ("f.bmp", b"BM" + b"\x00" * 100, "image/bmp")}), {422})
    step("diagnose extra field → 422 G2", c.post("/v1/diagnose", headers=K, data={"camera_id": "CAM-DEMO-01", "note": "x"}, files={"frame": ("f.jpg", synth_frame(), "image/jpeg")}), {422})
    step("diagnose unknown camera → 404 G3", c.post("/v1/diagnose", headers=K, data={"camera_id": "CAM-XX"}, files={"frame": ("f.jpg", synth_frame(), "image/jpeg")}), {404})
    # 실측·후속 차량
    step("measurement platform cam → 409 G10", c.post("/v1/measurements", headers=K, data={"vehicle_id": "1234", "camera_id": "CAM-S03"}, files={"frame": ("f.jpg", synth_frame(), "image/jpeg")}), {409})
    step("measurement 1234/CAM-DEMO-01", c.post("/v1/measurements", headers=K, data={"vehicle_id": "1234", "camera_id": "CAM-DEMO-01"}, files={"frame": ("f.jpg", synth_frame(persons=3), "image/jpeg")}), {200})
    r = step("measurement 1234/CAM-DEMO-02", c.post("/v1/measurements", headers=K, data={"vehicle_id": "1234", "camera_id": "CAM-DEMO-02"}, files={"frame": ("f.jpg", synth_frame(persons=1), "image/jpeg")}), {200})
    if r.status_code == 200:
        m = r.json()["measurement"]; print("     →", {k: m[k] for k in ("vacant_ratio_agg", "crowding_level_agg", "coverage_num", "coverage_den", "applied_validity_minutes", "expires_at", "demo_mode")})
    r = step("next-vehicle R102/3001", c.get("/v1/next-vehicle", headers=K, params={"route_id": "R102", "stop_id": "3001", "limit": 4}), {200})
    if r.status_code == 200:
        for v in r.json()["vehicles"]:
            print("     →", v["vehicle_id"], v["basis_type"], v.get("vacant_ratio"), v.get("crowding_level"), v.get("coverage_num"), v.get("coverage_den"))
    step("next-vehicle bad stop → 404 G11", c.get("/v1/next-vehicle", headers=K, params={"route_id": "R102", "stop_id": "9999"}), {404})
    step("ops-status", c.get("/v1/admin/ops-status", headers=A), {200})
    step("gate-events", c.get("/v1/admin/gate-events", headers=A), {200})
    step("detector", c.get("/v1/admin/detector", headers=A), {200})
    step("api-guide", c.get("/v1/api-guide"), {200})
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
