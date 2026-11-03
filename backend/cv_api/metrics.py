"""Prometheus 지표 — GET /metrics (내부 포트에서만, 기본 9524).

- HTTP 요청 수·처리 시간: 경로는 라우트 틀(`/v1/admin/cameras/{camera_id}`)로 묶는다 — 실제 ID 를 라벨에 넣으면 시계열이 끝없이 늘어난다
- 진단 결과 등급 수: free·normal·crowded·uncertain
- 검출기 상태: 준비 여부·적재 시간·최근 추론 시간 (긁을 때마다 runtime 에서 읽는다)
- 대전 BIS 오늘 호출 수 (공공데이터포털 일일 한도 점검)
- 백엔드 프로세스 CPU·메모리 (prometheus_client 기본 수집기)

라벨에 원본 프레임·키·토큰·아이디·IP 를 넣지 않는다 (FR-11).
API 안내 대조(G17) 대상이 아니다 — include_in_schema=False 라 openapi 에 나오지 않는다.
"""
from __future__ import annotations

from collections.abc import Iterable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    disable_created_metrics,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily, Metric

from .settings import get_settings

disable_created_metrics()   # *_created 시계열은 대시보드에 쓰지 않는다
REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)    # process_cpu_seconds_total, process_resident_memory_bytes …
PlatformCollector(registry=REGISTRY)   # python_info

HTTP_REQUESTS = Counter(
    "cv_http_requests_total", "HTTP 요청 수", ["method", "route", "status"], registry=REGISTRY,
)
HTTP_DURATION = Histogram(
    "cv_http_request_duration_seconds", "HTTP 요청 처리 시간(초)", ["method", "route"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),   # 2.0 = NFR-01 p95 약속
    registry=REGISTRY,
)
DIAGNOSES = Counter(
    "cv_diagnoses_total", "진단 결과 수 (혼잡 등급별)", ["level"], registry=REGISTRY,
)


class _RuntimeCollector:
    """긁을 때마다 현재 값을 읽는다 — 서비스 코드에 지표 갱신을 끼워 넣지 않는다."""

    def collect(self) -> Iterable[Metric]:
        from .external import bis
        from .services.ops import runtime

        st = runtime.state
        yield GaugeMetricFamily("cv_detector_loaded", "검출기 적재·웜업 완료 1, 아니면 0", value=1 if st.loaded else 0)
        if st.load_seconds is not None:
            yield GaugeMetricFamily("cv_detector_load_seconds", "검출기 적재에 걸린 시간(초)", value=st.load_seconds)
        if st.last_infer_ms is not None:
            yield GaugeMetricFamily("cv_detector_last_infer_ms", "가장 최근 추론 시간(ms)", value=st.last_infer_ms)
        yield GaugeMetricFamily("cv_bis_calls_today", "대전 BIS 오늘(한국 날짜) 실제 호출 수", value=bis.calls_today())


REGISTRY.register(_RuntimeCollector())


def route_of(request: Request) -> str:
    """라우트 틀. 맞는 라우트가 없으면(404) 'unmatched' — 존재하지 않는 경로가 라벨을 늘리지 않게."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def observe(request: Request, status: int, seconds: float, level: str | None) -> None:
    route = route_of(request)
    if route == "/metrics":
        return   # 수집 요청 자체는 세지 않는다
    HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
    HTTP_DURATION.labels(request.method, route).observe(seconds)
    if level:
        DIAGNOSES.labels(level).inc()


def metrics_endpoint(request: Request) -> Response:
    """METRICS_PORTS 로 들어온 요청에만 답한다. 9544(외부 공개 포트)로 오면 404 — 지표가 밖으로 새지 않게."""
    server = request.scope.get("server") or (None, None)
    if server[1] not in get_settings().METRICS_PORTS:
        return Response(status_code=404)
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)