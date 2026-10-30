#!/usr/bin/env bash
# 배포 전 자동 검증 (NFR-07, T076): DDL 회귀 · 백엔드 테스트 · 계약-안내 대조 · 프론트 타입·테스트·빌드
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
source .venv/bin/activate 2>/dev/null || { echo "venv 없음: /opt/homebrew/bin/python3.11 -m venv .venv"; exit 1; }
fail=0
step() { printf '\n== %s\n' "$1"; }

step "1/5 백엔드 테스트 (DDL 회귀 29건, 규격·품질·게이트·실측·후속 차량·시연·계약 대조)"
(cd backend && python -m pytest -q -p no:cacheprovider) || fail=1

step "2/5 프론트 타입 검사"
(cd frontend && npx tsc -b) || fail=1

step "3/5 프론트 컴포넌트 테스트"
(cd frontend && npx vitest run --reporter=dot) || fail=1

step "4/5 프론트 빌드"
(cd frontend && npx vite build --logLevel warn) || fail=1

step "5/5 벤치 (백엔드가 9544 에서 떠 있을 때만)"
if curl -sf localhost:9544/v1/readiness >/dev/null 2>&1; then
  python backend/bench.py --n "${BENCH_N:-30}" || fail=1
else
  echo "서버 없음 — 벤치 생략 (cd backend && python -m cv_api.serve 후 재실행)"
fi

if [ "$fail" -eq 0 ]; then echo; echo "PREFLIGHT PASS"; else echo; echo "PREFLIGHT FAIL"; exit 1; fi
