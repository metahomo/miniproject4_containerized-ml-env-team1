# ==============================================================================
# [CPU 전용 시연 환경 빌드] - 버전 1.3
# * GPU 전환 시 베이스 이미지를 아래로 변경:
#   FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime
# ==============================================================================
FROM python:3.11-slim

LABEL maintainer="sumtong-team1" \
      version="1.3" \
      description="YOLO11 Bus Crowd & Distance Analysis Pipeline v1.3"

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    PYTHONPATH=/app \
    APP_VERSION="1.3"

# OpenCV 및 시스템 필수 라이브러리 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) PyTorch CPU 전용 휠 설치 (이미지 용량 및 빌드 시간 절약)
# * GPU 전환 시(공식 PyTorch CUDA 이미지 사용 시) 아래 RUN 블록 주석 처리
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.2.0 torchvision==0.17.0

# 2) 파이썬 라이브러리 설치
COPY requirements.txt ./
# torch, torchvision, nvidia 관련 패키지 중복/충돌 설치 방지 및 CPU 인덱스 유지
RUN grep -vE '^(torch|torchvision|nvidia-)==' requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir \
       --extra-index-url https://download.pytorch.org/whl/cpu \
       -r /tmp/req.txt \
    && rm -f /tmp/req.txt

# 3) 소스코드 복사 (빌드 컨텍스트를 13-yolo11-distance 폴더 자체로 단순화)
COPY src ./src
COPY scripts ./scripts

# 기본 모델/데이터/결과 마운트 디렉터리 생성
RUN mkdir -p /app/backend/models /app/backend/samples /app/data /app/datasets /app/results

# 기본 실행 명령: 융합 추론 스크립트 도움말 출력
CMD ["python", "scripts/test_dual_vacancy.py", "--help"]
