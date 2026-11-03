# YOLO11 버스 객실 분석 파이프라인 Docker 가이드 (v1.2)

본 문서는 **13-yolo11-distance** 파이프라인(객체 거리 측정, 이중 모델 융합 추론, 데이터 증강 및 파인튜닝)의 도커 환경 구축 및 실행 방법을 안내합니다.

* **도커 이미지 태그**: `yolo11-bus-distance:1.2` (CPU 기본) / `yolo11-bus-distance:1.2-gpu` (GPU 운영용)
* **릴리스 버전**: `v1.2` (혼잡도 % 공식 일치, `CV_MODELS_DIR` 환경 변수 및 디바이스 자동 감지)

---

## 1. 현재 환경 (CPU 시연 모드 - v1.2)

### 1) 이미지 빌드
프로젝트 루트(`sumtong/`) 또는 `13-yolo11-distance/` 폴더에서 빌드를 수행합니다.
```bash
# 루트 폴더에서 실행 시
docker compose -f 13-yolo11-distance/docker-compose.yml build
```

### 2) 버전 확인
컨테이너 내부의 1.2 버전 엔진 확인:
```bash
docker compose -f 13-yolo11-distance/docker-compose.yml run --rm yolo11-runner \
  python scripts/test_dual_vacancy.py --version
# 출력: YOLO11 Bus Distance Pipeline v1.2
```

### 3) 이중 모델 융합 추론 실행
`docker-compose.yml`에 볼륨 마운트와 환경 변수(`CV_MODELS_DIR`)가 정의되어 있으므로 `docker compose run`으로 간편하게 실행합니다.
```bash
# 샘플 이미지(data/sample.jpg) 추론
docker compose -f 13-yolo11-distance/docker-compose.yml run --rm yolo11-runner \
  python scripts/test_dual_vacancy.py --source /app/data/sample.jpg --out /app/results/output_sample.jpg

# 백엔드 버스 샘플(bus_empty.jpg / bus_full.jpg) 추론
docker compose -f 13-yolo11-distance/docker-compose.yml run --rm yolo11-runner \
  python scripts/test_dual_vacancy.py --source /app/backend/samples/bus_full.jpg --out /app/results/dual_full.jpg
```

### 4) 단독 docker run 명령어로 실행할 경우
```bash
docker run --rm \
  -e CV_MODELS_DIR=/app/backend/models \
  -v ${PWD}/backend/models:/app/backend/models:ro \
  -v ${PWD}/13-yolo11-distance/data:/app/data:ro \
  -v ${PWD}/13-yolo11-distance/results:/app/results \
  yolo11-bus-distance:1.2 \
  python scripts/test_dual_vacancy.py --source /app/data/sample.jpg --out /app/results/output.jpg
```

---

## 2. ★ GPU 환경 전환 시 수정해야 하는 부분 (기록)

### [수정 1] Dockerfile 베이스 이미지 및 PyTorch 설치 변경
**CPU (현재 v1.2):**
```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.2.0 torchvision==0.17.0
```

**GPU (전환 시):**
```dockerfile
FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime
# 공식 이미지에 PyTorch + CUDA + cuDNN이 내장되어 있으므로 별도의 torch 설치 RUN 명령어는 주석 처리합니다.
# (주의: requirements.txt 설치 단계의 --extra-index-url https://download.pytorch.org/whl/cpu 줄도 함께 제거합니다.)
```

### [수정 2] docker-compose.yml GPU 리소스 예약 주석 해제
`yolo11-runner` 서비스 하위의 `deploy` 블록 주석을 해제하고 이미지 태그를 `:1.2-gpu`로 변경합니다.
```yaml
    image: yolo11-bus-distance:1.2-gpu
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

### [수정 3] 단독 docker run 사용 시 GPU 플래그 추가
`docker compose`가 아닌 `docker run` 직접 실행 시 `--gpus all` 옵션을 추가합니다:
```bash
docker run --rm --gpus all ...
```

### [수정 4] 디바이스 인식 확인 및 학습/추론 실행
**컨테이너 내 GPU 인식 검증:**
```bash
docker compose -f 13-yolo11-distance/docker-compose.yml run --rm yolo11-runner \
  python -c "import torch; print('CUDA Available:', torch.cuda.is_available())"
```

* **추론 파이프라인**: `dual_pipeline.py` 내부에서 `torch.cuda.is_available()`을 자동 감지하므로 별도 옵션 변경 없이 즉시 GPU 가속이 적용됩니다.
* **학습 스크립트 실행 시**:
  * **GPU**: `python scripts/train_bus.py --device 0`
  * **CPU**: `python scripts/train_bus.py --device cpu`
