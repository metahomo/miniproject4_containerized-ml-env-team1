"""시연 카메라를 지금 도착 예정인 102번 버스로 다시 연결 (T097) — S8 «102번 운행 차량으로 다시 연결» 버튼과 같다.

사용: python scripts/demo_bis_remap.py [--web-base http://localhost:9524] (관리자 키: 환경변수 CV_ADMIN_KEY 또는 키 파일 — 명령행 인자로는 받지 않는다)
                                      [--route 30300037] [--stop 30300037:42620] [--cameras CAM-DEMO-01,CAM-DEMO-02,CAM-DEMO-03]
  --stop 30300037:42600 → 충남대학교 (온천교 방면)
도착 정보가 없으면(첫차 전·막차 후·연계 장애) 아무것도 바꾸지 않고 알린다. 서버는 EXTERNAL_PROVIDER=bis 로 떠 있어야 한다.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

import httpx
from _split_client import env_keys


def kst(iso: str | None) -> str:
    if not iso:
        return "—"
    return (datetime.fromisoformat(iso) + timedelta(hours=9)).strftime("%H:%M")


def main() -> int:
    ap = argparse.ArgumentParser(description="시연 카메라 → 도착 예정 BIS 차량 다시 연결")
    ap.add_argument("--web-base", default="http://localhost:9524")
    ap.add_argument("--route", default="30300037"); ap.add_argument("--stop", default="30300037:42620")
    ap.add_argument("--cameras", default="CAM-DEMO-01,CAM-DEMO-02,CAM-DEMO-03")
    a = ap.parse_args()
    body = {"route_id": a.route, "stop_id": a.stop, "camera_ids": [c.strip() for c in a.cameras.split(",") if c.strip()]}
    r = httpx.post(f"{a.web_base}/v1/admin/demo/bis-remap", headers={"X-Admin-Key": env_keys()[1]}, json=body, timeout=30)
    j = r.json()
    if r.status_code != 200:
        print(f"실패 HTTP {r.status_code}: {j.get('reason', j)}")
        return 1
    print(f"{j['message']}  (노선 {j['route_id']} · 정류장 {j['stop_id']} · 연계 {j['source_status']})")
    for x in j["rows"]:
        print(f"  {x['camera_id']:<12} {x['before'] or '(없음)':<14} → {x['after'] or '(없음)':<14} 도착 {kst(x['expected_arrival_at'])} KST  [{x['action']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
