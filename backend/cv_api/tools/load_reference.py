"""기준 정보 적재 — TAGO CSV → route·stop UPSERT (research R12, G11 판정 원천).

사용: python -m cv_api.tools.load_reference [--routes data/routes.csv] [--stops data/stops.csv]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import text

from .. import db
from ..settings import BACKEND_DIR


def load(routes_csv: Path, stops_csv: Path) -> dict:
    db.init_db()
    n_r = n_s = 0
    with db.connect() as conn:
        with open(routes_csv, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    text("INSERT INTO route (route_id, mode, route_name, source) VALUES (:route_id, :mode, :route_name, :source) "
                         "ON CONFLICT(route_id) DO UPDATE SET mode=excluded.mode, route_name=excluded.route_name, source=excluded.source"),
                    {k: row.get(k) for k in ("route_id", "mode", "route_name", "source")} | {"source": row.get("source") or "TAGO"},
                )
                n_r += 1
        with open(stops_csv, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    text("INSERT INTO stop (stop_id, route_id, stop_name, place_kind) VALUES (:stop_id, :route_id, :stop_name, :place_kind) "
                         "ON CONFLICT(stop_id) DO UPDATE SET route_id=excluded.route_id, stop_name=excluded.stop_name, place_kind=excluded.place_kind"),
                    {k: row.get(k) for k in ("stop_id", "route_id", "stop_name", "place_kind")},
                )
                n_s += 1
    return {"routes": n_r, "stops": n_s}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", default=str(BACKEND_DIR / "data" / "routes.csv"))
    ap.add_argument("--stops", default=str(BACKEND_DIR / "data" / "stops.csv"))
    a = ap.parse_args()
    print(load(Path(a.routes), Path(a.stops)))


if __name__ == "__main__":
    main()
