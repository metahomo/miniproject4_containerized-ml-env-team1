"""BIS 체계 기준 정보 받기 (결정 D5) — 대전 BIS 공공 API 의 노선·경유 정류소를 load_reference 가 읽는 CSV 로 쓴다.

사용 (backend/ 에서, .env 의 BIS_API_KEY 사용):
    python -m cv_api.tools.fetch_bis_reference                       # 전체 노선 (API 호출 ≈ 노선 수 + 2)
    python -m cv_api.tools.fetch_bis_reference --routes 30300001,102 # 일부 노선 (ROUTE_CD 또는 겹치지 않는 노선 번호)
    python -m cv_api.tools.load_reference --routes data/bis_routes.csv --stops data/bis_stops.csv

식별 규칙 (research R12, UC_00 §8.3 29):
- route_id = ROUTE_CD (8자리). 노선 번호는 겹치므로 route_name 에만 쓴다.
- route_name = «102번 · 간선 · 원골↔수통골 (30300037)» — 번호가 같은 노선(1번이 3개 등)을 이용자가 구분하게 유형·기점↔반환점을
  붙인다(2026-09-30). 유형은 번호 체계로 확인되는 급행(1)·간선(2)·지선(4)만 — 나머지 ROUTE_TP 는 공식 코드표 미확인이라 비운다.
  기점↔반환점은 START_STOP_ID·TURN_STOP_ID(없으면 경유 순서의 가운데 정류소)의 이름.
- stop_id = "ROUTE_CD:BUS_STOP_ID". `stop` 테이블은 정류장 하나가 노선 하나에 속하는 구조인데 BIS 정류소는 여러 노선이 공유한다.
  스키마를 바꾸지 않고 노선별로 구분하려고 합성한다. BisProvider 는 ':' 뒤를 BUS_STOP_ID 로 읽는다.
시연용 fixture(R102/3001)와 섞여도 충돌하지 않는다. 적재해도 EXTERNAL_PROVIDER 는 바꾸지 않는다(전환은 운영 관리자가 .env 에서).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..external.bis import BisProvider
from ..settings import BACKEND_DIR, Settings, get_settings


ROUTE_TYPE = {"1": "급행", "2": "간선", "4": "지선"}   # ROUTE_TP — 확인된 것만 (나머지 3·5~9 는 코드표 확인 필요)


def route_label(r: Dict[str, str], seq: List[Dict[str, str]]) -> str:
    """노선 한 줄 이름. seq = 경유 정류소(순서대로, BUS_STOP_ID·BUSSTOP_NM)."""
    cd, no = r.get("ROUTE_CD", ""), (r.get("ROUTE_NO") or "").strip()
    name = {st.get("BUS_STOP_ID"): (st.get("BUSSTOP_NM") or "").strip() for st in seq}
    start = name.get(r.get("START_STOP_ID")) or (name.get(seq[0].get("BUS_STOP_ID")) if seq else "")
    turn = name.get(r.get("TURN_STOP_ID")) or (name.get(seq[len(seq) // 2].get("BUS_STOP_ID")) if seq else "")
    parts = [f"{no}번"] + ([ROUTE_TYPE[r["ROUTE_TP"]]] if r.get("ROUTE_TP") in ROUTE_TYPE else [])
    if start and turn and start != turn:
        parts.append(f"{start}↔{turn}")
    elif start:
        parts.append(f"{start} 순환")
    return f"{' · '.join(parts)} ({cd})"


def collect(p: BisProvider, only: Optional[Sequence[str]] = None) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    routes: List[Dict[str, str]] = []
    page, pages = 1, 1
    while page <= pages:
        items, pages = p._get_page("busRouteInfo/getRouteInfoAll", reqPage=page)
        routes += items
        page += 1
    if only:
        codes = {p._route_cd(r) for r in only}
        routes = [r for r in routes if r.get("ROUTE_CD") in codes]
    route_rows, stop_rows = [], []
    for r in routes:
        cd = r.get("ROUTE_CD", "")
        seq = [st for st in p._stations(cd) if st.get("BUS_STOP_ID")]
        route_rows.append({"route_id": cd, "mode": "bus", "route_name": route_label(r, seq), "source": "BIS"})
        names = [(st.get("BUSSTOP_NM") or "").strip() for st in seq]
        for i, st in enumerate(seq):
            name = names[i]
            if names.count(name) > 1:   # 같은 이름이 양방향에 있다 → 다음 정류장으로 방향을 붙인다 (이용자가 고를 수 있게, T099)
                name = f"{name} ({names[i + 1]} 방면)" if i + 1 < len(names) else f"{name} (종점)"
            stop_rows.append({"stop_id": f"{cd}:{st['BUS_STOP_ID']}", "route_id": cd, "stop_name": name, "place_kind": "bus_stop"})
    return route_rows, list({s["stop_id"]: s for s in stop_rows}.values())   # 순환 노선의 같은 정류소 중복 제거


def write(rows: List[Dict[str, str]], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)


def main(argv: Optional[Sequence[str]] = None, s: Optional[Settings] = None) -> Dict[str, int]:
    ap = argparse.ArgumentParser(description="대전 BIS 노선·경유 정류소 → 기준 정보 CSV")
    ap.add_argument("--routes", default="", help="쉼표 구분 ROUTE_CD 또는 노선 번호. 비우면 전체")
    ap.add_argument("--out-dir", default=str(BACKEND_DIR / "data"))
    a = ap.parse_args(argv)
    p = BisProvider(s or get_settings())
    route_rows, stop_rows = collect(p, [x.strip() for x in a.routes.split(",") if x.strip()] or None)
    out = Path(a.out_dir)
    write(route_rows, out / "bis_routes.csv")
    write(stop_rows, out / "bis_stops.csv")
    print(f"노선 {len(route_rows)} · 정류장 {len(stop_rows)} → {out}/bis_routes.csv, bis_stops.csv")
    return {"routes": len(route_rows), "stops": len(stop_rows)}


if __name__ == "__main__":
    main()
