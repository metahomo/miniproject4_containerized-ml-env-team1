# scripts/train — 차내 머리 검출 학습

만원 버스·전철 안에서는 발·몸이 가려져 사람(person) 검출이 인원을 적게 센다. 그래서 **머리(head)** 를 검출하도록
YOLOv8 을 추가 학습한다. 서비스는 가중치의 클래스 이름이 `head` 이면 자동으로 머리 모드가 되어
ROI 판정 기준점을 **박스 중심**으로 바꾼다(`cv_api/predict.py` `resolve_target`·`anchor_points`, `MODEL_TARGET=auto`).

실행은 모두 프로젝트 루트에서, 가상환경 파이썬으로 한다: `.venv/bin/python scripts/train/<스크립트>.py ...`
(`.venv` 에 ultralytics 8.4·torch 2.14·MPS 가 있다). 데이터·결과(`datasets/`, `runs/`)는 커밋하지 않는다(.gitignore).

## 전체 흐름

| 단계 | 스크립트 | 하는 일 |
|---|---|---|
| 1 | `extract_frames.py` | 차내 CCTV 영상 → 3초마다 1장, 흐린 장면 제외, 이름 `<출처>__<카메라>__<날짜>__<t>.jpg` |
| 2 | `convert_public.py` | 공개 머리 데이터(CrowdHuman·SCUT-HEAD) → YOLO 형식 (1차 학습용) |
| 3 | `autolabel.py` | 머리 모델로 자동 라벨 → CVAT 에서 사람이 고침 |
| 4 | `split.py` | 라벨 끝난 pool → train/val/test (카메라·날짜 그룹 단위) + `data.yaml` |
| 5 | `train.py` | 1차 공개 데이터 → 2차 차내 데이터 순서로 학습 (imgsz 1280, mps) |
| 6 | `eval_count.py` | 프레임당 인원 오차(MAE)·SC-01 로 기존 모델과 비교, 인원 세기 기준 추천 |

```bash
# 1차: 공개 데이터로 머리 모델 만들기
.venv/bin/python scripts/train/convert_public.py crowdhuman --odgt datasets/raw/crowdhuman/annotation_train.odgt \
    --images datasets/raw/crowdhuman/Images --out datasets/crowdhuman_head --split train
.venv/bin/python scripts/train/convert_public.py crowdhuman --odgt datasets/raw/crowdhuman/annotation_val.odgt \
    --images datasets/raw/crowdhuman/Images --out datasets/crowdhuman_head --split val
.venv/bin/python scripts/train/train.py --data datasets/crowdhuman_head/data.yaml --name crowdhuman --epochs 60

# 2차: 차내 데이터
.venv/bin/python scripts/train/extract_frames.py 버스영상.mp4 --source daejeon-bus --camera CAM-B101 --date 20261001 \
    --out datasets/transit_head/images/pool
.venv/bin/python scripts/train/autolabel.py --weights runs/head/crowdhuman/weights/best.pt \
    --images datasets/transit_head/images/pool --cvat-zip datasets/transit_head/pool_cvat.zip
#   → CVAT 에서 고친 뒤 YOLO 1.1 로 내보내 labels/pool/ 에 덮어쓰기
.venv/bin/python scripts/train/split.py datasets/transit_head
.venv/bin/python scripts/train/train.py --data datasets/transit_head/data.yaml --name transit \
    --weights runs/head/crowdhuman/weights/best.pt --epochs 100 --lr0 0.002
.venv/bin/python scripts/train/eval_count.py --data datasets/transit_head/data.yaml --split test --capacity 80 \
    --weights runs/head/transit/weights/best.pt runs/head/crowdhuman/weights/best.pt backend/models/yolov8n.pt
```

## 데이터

- **차내 영상(핵심)**: 대전 시내버스·도시철도 차내 CCTV. 기관 승인·개인정보 처리 근거·가명처리 협의가 먼저다
  (서비스의 FR-11 원본 미저장 규칙과 별개). 출퇴근 만원·한산·야간·역광·창 반사를 고루, 카메라 유형(버스 앞·뒤, 전철 칸)마다
  수백 장 이상. 처음 목표 1,500~3,000장.
- **공개 데이터(보조)**
  | 데이터 | 받는 곳 | 라이선스 | 비고 |
  |---|---|---|---|
  | CrowdHuman | huggingface.co/datasets/sshao0516/CrowdHuman (train 8.4GB·val 2.5GB) | **CC BY-NC 4.0 (비상업)** | 머리 박스 `hbox`. 운영 배포 가중치에 쓸 수 있는지 발주 측 확인 필요 |
  | SCUT-HEAD | github.com/HCIILAB/SCUT-HEAD-Dataset-Release | 연구용 | 교실·위에서 본 머리. VOC xml → `convert_public.py voc` |

## 라벨링 규칙 (모든 작업자 공통)

1. 머리가 **일부라도 보이면** 표시한다 (뒤통수·모자·반쯤 가린 머리 포함). 박스는 보이는 머리 영역만.
2. **표시하지 않는 것**: 창밖 사람, 유리·스테인리스에 비친 사람, 광고·포스터 속 사람, 운전석 칸막이 너머 기사(차량 정원에 들지 않음).
3. 너무 작아 머리인지 알 수 없으면(대략 8px 미만) 표시하지 않는다.
4. 사람이 없는 장면도 빈 라벨로 남긴다 — 오검출을 줄인다.
5. 애매하면 표시하지 말고 메모 → 라벨 규칙을 같이 고친다. 규칙이 바뀌면 이 절을 고친다.

## 6. 서비스 반영

1. `eval_count.py` 에서 새 모델이 기존(yolov8n person)보다 MAE 가 작고 SC-01 이 목표(85%)에 가까운지 확인.
2. `cp runs/head/transit/weights/best.pt backend/models/head_transit_n1280.pt`
3. `backend/.env`: `MODEL_WEIGHTS=models/head_transit_n1280.pt` (`MODEL_TARGET=auto` 그대로 — 클래스 이름 head 로 머리 모드),
   `COUNT_CONF_MIN=<eval 추천값>`. 운영 중에는 S3 등급 기준의 인원 세기 기준도 같은 값으로.
4. `backend/models/model_package.json`·`backend/cv_api/guide/model_card.md` 의 가중치·검증 결과 갱신.
5. `cd backend && ../.venv/bin/python -m pytest`, `scripts/preflight.sh`, 서버 재기동(`python -m cv_api.serve --host 0.0.0.0`).
6. 라이선스: 파인튜닝 가중치도 Ultralytics 가중치의 파생물 → **AGPL-3.0**. 학습 데이터 라이선스(CrowdHuman 비상업)도 함께 기록.
