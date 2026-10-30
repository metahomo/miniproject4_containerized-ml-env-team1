# syntax=docker/dockerfile:1
# 웹 프론트 이미지 — 빌드한 화면을 nginx 가 9504 로 내주고 /v1 등은 백엔드로 넘긴다 (nginx/default.conf.template).
# 빌드 컨텍스트는 저장소 루트(.dockerignore 공용):
#   docker build -f frontend/Dockerfile -t hyungnss/sumtong:frontend-<판> .
# VITE_API_BASE 는 비운 채 빌드한다 — 화면이 «접속한 주소의 /v1» 로 부르므로 어느 PC 에서든 같은 이미지가 돈다. 키는 넣지 않는다.

# 1) 빌드 — 결과물(dist/)은 CPU 종류와 무관하므로 빌드하는 PC 의 플랫폼에서 한 번만 돈다(arm64 에뮬레이션 없음)
FROM --platform=$BUILDPLATFORM node:22-alpine AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

# 2) 실행 — root 가 아닌 nginx
FROM nginxinc/nginx-unprivileged:stable-alpine
# 백엔드 주소(호스트:포트) — compose 서비스 이름. 다른 곳의 백엔드면 실행할 때 바꾼다
ENV BACKEND_WEB=backend:9524 \
    BACKEND_API=backend:9544
COPY frontend/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 9504
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:9504/ || exit 1
