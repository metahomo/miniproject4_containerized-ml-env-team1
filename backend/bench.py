"""bench.py (T032 · 2026-09-30 C8 개정) — POST /v1/diagnose 응답 시간. 팀이 «같은 자»로 다시 잰다 — 절차를 바꾸면 이전 숫자와 비교할 수 없다.

절차 (API 점검 2026-09-30 과 같다):
  readiness=ready 확인 → 1~5번째 요청 기록(첫 요청 비율 SC-04 · 두 번째) 후 «버림» → 단건 n회(기본 100) 순차
  → 정렬해 p50 = 50번째, p95 = 95번째 (NFR-01: p95 ≤ 2초) → 선택: 동시 10건 × 3회(--concurrent)
예시 요청 고정: samples/bench_frame.jpg (버스 차내 854×480 JPEG 86,683 B, 공개 샘플 영상 3초 지점) · 카메라 CAM-DEMO-01.

키는 명령행 인자로 받지 않는다 (ps 로 다른 사용자에게 보인다, 점검 D8). 읽는 순서:
  환경변수 CV_API_KEY(X-API-Key) → CV_ADMIN_KEY(X-Admin-Key) → 키 파일 CV_KEY_FILE(기본 backend/.logs/ADMIN_KEY.txt 의 ADMIN_KEY= 줄)
사용: python backend/bench.py [--base http://127.0.0.1:9544] [--camera CAM-DEMO-01] [--n 100] [--frame path.jpg] [--concurrent]
주의: 요청마다 진단 기록(diagnosis_request·assessment)이 남는다. 원본 프레임은 저장되지 않는다(FR-11).
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
DEFAULT_FRAME = HERE / "samples" / "bench_frame.jpg"
DEFAULT_KEY_FILE = HERE / ".logs" / "ADMIN_KEY.txt"


def auth_headers() -> dict:
    if os.environ.get("CV_API_KEY"):
        return {"X-API-Key": os.environ["CV_API_KEY"]}
    if os.environ.get("CV_ADMIN_KEY"):
        return {"X-Admin-Key": os.environ["CV_ADMIN_KEY"]}
    f = Path(os.environ.get("CV_KEY_FILE", DEFAULT_KEY_FILE))
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("ADMIN_KEY="):
                return {"X-Admin-Key": line.split("=", 1)[1].strip()}
    sys.exit("키 없음 — 환경변수 CV_API_KEY 또는 CV_ADMIN_KEY, 또는 키 파일 CV_KEY_FILE 을 둔다 (명령행 인자로는 받지 않는다)")


def pct(xs: list, p: int) -> float:
    s = sorted(xs)
    return s[max(0, int(len(s) * p / 100) - 1)]          # 정렬해 p 번째 (n=100 이면 50·95번째)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:9544")
    ap.add_argument("--camera", default="CAM-DEMO-01")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--frame", default=str(DEFAULT_FRAME))
    ap.add_argument("--concurrent", action="store_true", help="동시 10건 × 3회도 잰다")
    a = ap.parse_args()
    data = Path(a.frame).read_bytes()
    c = httpx.Client(base_url=a.base, timeout=120, headers=auth_headers())
    r = c.get("/v1/readiness").json()
    det = r.get("detector") or {}
    print(f"readiness: {r['readiness']} | detector: {det.get('kind')} {det.get('model')} | model_commit {r.get('model_commit')}")
    if r["readiness"] != "ready":
        sys.exit("준비 안 됨 — 재지 않는다")

    def one() -> tuple:
        t0 = time.perf_counter()
        res = c.post("/v1/diagnose", data={"camera_id": a.camera}, files={"frame": ("bench.jpg", data, "image/jpeg")})
        return (time.perf_counter() - t0) * 1000, res

    first5 = []
    for _ in range(5):                                      # 워밍업 — 기록만 하고 p50·p95 에서는 버린다
        ms, res = one()
        if res.status_code != 200:
            sys.exit(f"요청 실패: {res.status_code} {res.text[:200]}")
        first5.append(ms)
    times, levels = [], {}
    for _ in range(a.n):
        ms, res = one()
        if res.status_code != 200:
            sys.exit(f"요청 실패: {res.status_code} {res.text[:200]}")
        times.append(ms)
        lv = res.json()["crowding_level"]
        levels[lv] = levels.get(lv, 0) + 1
    p50, p95 = pct(times, 50), pct(times, 95)
    warm = statistics.mean(first5[1:])
    print(f"\n{'구간':24s} {'값':>10s}  기준")
    print(f"{'첫 요청 (1번째)':24s} {first5[0]:8.1f} ms  2~5번째 평균 {warm:.1f} ms 의 {first5[0] / warm:.2f}배 (≤ 3배)")
    print(f"{'두 번째':24s} {first5[1]:8.1f} ms")
    print(f"{'단건 p50':24s} {p50:8.1f} ms  n={a.n} (워밍업 5건 버림)")
    print(f"{'단건 p95':24s} {p95:8.1f} ms  NFR-01 ≤ 2000 ms → {'PASS' if p95 <= 2000 else 'FAIL'}")
    print(f"{'min · max · mean':24s} {min(times):.1f} · {max(times):.1f} · {statistics.mean(times):.1f} ms")
    print(f"{'처리량(순차)':24s} {a.n / (sum(times) / 1000):8.2f} rps")
    print(f"{'등급 분포':24s} {levels}")
    if a.concurrent:
        conc, fail = [], 0
        for _ in range(3):
            with ThreadPoolExecutor(10) as ex:
                out = list(ex.map(lambda _: one(), range(10)))
            conc += [ms for ms, _ in out]
            fail += sum(1 for _, res in out if res.status_code != 200)
        print(f"{'동시 10 × 3회':24s} 실패 {fail} · p50 {pct(conc, 50):.1f} ms · p95 {pct(conc, 95):.1f} ms · max {max(conc):.1f} ms")


if __name__ == "__main__":
    main()
