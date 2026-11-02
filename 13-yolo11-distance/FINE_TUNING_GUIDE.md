# 🚍 버스 객실 특화 YOLO 이중 모델 추가 학습(Fine-Tuning) 가이드

본 문서는 일반 데이터셋(COCO/CrowdHuman) 기반 모델의 버스 객실 내 미검출(False Negative) 한계를 극복하고, 버스 환경에 최적화된 이중 모델(YOLOv8 Head + YOLO11 Body)을 추가 학습하기 위한 5단계 가이드입니다.

---

## ⚡ 1. [긴급 조치] 파라미터 최적화 (훈련 없이 즉시 적용)

추가 학습 전에 모델의 입력 해상도 및 신뢰도 임계값을 조정하여 탐지율을 즉각적으로 개선할 수 있습니다.

* **원인:** `head_crowdhuman_n1280.pt` 모델은 1280 해상도 기반으로 설계되었으나, 기본 640 해상도로 축소 입력되고 높은 Confidence 임계값(0.20)으로 인해 가려진 머리가 제외됨.
* **조치 내용:** 
  - `head_imgsz=1280` 적용
  - `head_conf=0.12` (또는 0.10)로 완화
  - `person_conf=0.15`로 완화

### 긴급 조치 테스트 실행 명령어:
```bash
# 기본 파라미터 적용 (imgsz=1280, head_conf=0.12, person_conf=0.15)
python scripts/test_dual_vacancy.py --source ../backend/samples/bus_full.jpg --out results/dual_full_fixed.jpg

# 더 민감하게 탐지하고자 할 때 (정원 20명, head_conf 0.10)
python scripts/test_dual_vacancy.py --source ../backend/samples/bus_full.jpg --out results/dual_full_fixed.jpg --capacity 20 --head-conf 0.10
```

---

## 🛠️ 2. 혼잡 버스 맞춤형 모델 추가 학습 5단계 로드맵

### 1단계: 데이터 수집 및 차내 특화 라벨링
* **수집:** 실제 버스 내부 블랙박스/CCTV 캡처 이미지 (권장 500~1,000장 이상)
* **도구:** Roboflow 또는 CVAT (YOLO format export)
* **클래스 정의:**
  - `0`: `head` (가려진 뒷모습, 옆모습, 모자 착용 포함)
  - `1`: `person` (좌석 착석 승객, 겹쳐진 전신/상반신)

### 2단계: 데이터셋 분할 및 배치
수집한 이미지와 `.txt` 라벨을 한 폴더(예: `raw_bus_data/`)에 모은 후, 자동 분할 스크립트를 실행합니다:
```bash
python scripts/split_bus_dataset.py --src-dir <데이터_폴더_경로> --val-ratio 0.2
```
* 결과는 자동으로 `datasets/bus_crowd/images/train`, `images/val`, `labels/train`, `labels/val`에 배치됩니다.

### 3단계: 메타데이터 설정
`datasets/bus_crowd/data.yaml` 파일이 이미 세팅되어 있습니다:
```yaml
path: datasets/bus_crowd
train: images/train
val: images/val

names:
  0: head
  1: person
```

### 4단계: 파인튜닝 실행 (학습)
데이터셋이 준비되면 다음 명령어로 학습을 시작합니다:
```bash
# 기본 50 에포크 학습
python scripts/train_bus.py --epochs 50

# GPU 번호 지정 및 자동 배포까지 원스톱 실행
python scripts/train_bus.py --epochs 50 --device 0 --deploy
```

### 5단계: 결과 검증 및 실서비스 배포
`--deploy` 옵션을 사용하지 않은 경우 수동으로 가중치를 교체합니다:
```bash
# Model A (Head) 가중치 교체
cp runs/train/bus_head_v8/weights/best.pt ../backend/models/head_crowdhuman_n1280.pt

# Model B (Body) 가중치 교체
cp runs/train/bus_person_yolo11/weights/best.pt ../backend/models/yolo11n.pt

# 최종 파이프라인 검증
python scripts/test_dual_vacancy.py --source ../backend/samples/bus_full.jpg --out results/dual_full_final.jpg
```
