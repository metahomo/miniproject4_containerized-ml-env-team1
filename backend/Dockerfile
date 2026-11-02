# syntax=docker/dockerfile:1
# 백엔드 이미지 — 한 프로세스가 같은 전체 앱을 9544(외부 공개 API)·9524(웹 프록시 대상)로 연다 (R21-D1).
# 빌드 컨텍스트는 저장소 루트(DDL 이 design/ 에 있다):
#   docker build -f backend/Dockerfile -t hyungnss/sumtong:backend-<판> .
# 이미지에 없는 것(.dockerignore): .env·docker.env·DB·모델(models/ 는 볼륨) — docker.env.example 참고
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOLO_CONFIG_DIR=/home/app/.config/Ultralytics

# OpenCV 공유 라이브러리 — lock 에 opencv-python(ultralytics 의존)이 함께 있어 headless 만으로는 부족하다
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# torch 는 CPU 판을 먼저 — 기본 설치(CUDA)는 수 GB. lock 의 torch==2.14.0 은 2.14.0+cpu 로 충족된다
# pgserver 는 PostgreSQL 테스트 전용(pgtest)이고 linux/arm64 설치 파일이 없다 — 이미지에는 넣지 않는다
COPY backend/requirements.lock.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    TORCH=$(grep -E '^torch==' requirements.lock.txt) \
    && VISION=$(grep -E '^torchvision==' requirements.lock.txt) \
    && pip install --index-url https://download.pytorch.org/whl/cpu "$TORCH" "$VISION" \
    && grep -vE '^pgserver==' requirements.lock.txt > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

# 앱 — 코드는 BACKEND_DIR(/app/backend)·REPO_ROOT(/app) 기준으로 파일을 찾는다 (cv_api/settings.py)
COPY design/cv_ddl.sql design/cv_ddl.postgres.sql /app/design/
COPY backend/pyproject.toml ./
COPY backend/cv_api ./cv_api
COPY backend/data ./data
COPY backend/samples ./samples
# 시연 데이터 넣기: docker compose exec -e CV_ADMIN_KEY=<관리자 키 원문> backend python /app/scripts/demo_prepare.py
COPY scripts/demo_prepare.py scripts/_split_client.py /app/scripts/

# 전용 사용자 — DB(/data)·모델(models/, 볼륨)·ultralytics 설정 폴더만 쓸 수 있게
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /app/backend/models "$YOLO_CONFIG_DIR" \
    && chown -R app:app /data /app/backend/models /home/app/.config
USER app
VOLUME ["/data"]

EXPOSE 9544 9524

# readiness 는 기동 중에도 200(preparing) — 응답이 오면 살아 있는 것. 모델 적재·웜업에 20~60초
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9544/v1/readiness', timeout=4)"

# cv_api.serve 는 공개된 기본 키(changeme-…)면 시작을 거부한다 (BE-1) — docker.env 에 새 키를 넣는다
CMD ["python", "-m", "cv_api.serve", "--host", "0.0.0.0"]
