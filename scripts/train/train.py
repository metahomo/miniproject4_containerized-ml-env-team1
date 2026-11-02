"""5단계 — 머리 검출 학습 (Ultralytics YOLOv8, 클래스 1개 head).

  # 1차: 공개 데이터(CrowdHuman 머리)로 COCO 가중치에서 출발
  python scripts/train/train.py --data datasets/crowdhuman_head/data.yaml --name crowdhuman --epochs 60

  # 2차: 우리 차내 데이터로 1차 결과를 이어서 (적은 데이터라 학습률 낮게)
  python scripts/train/train.py --data datasets/transit_head/data.yaml --name transit \
      --weights runs/head/crowdhuman/weights/best.pt --epochs 100 --lr0 0.002

- imgsz 는 서비스 설정 MODEL_IMGSZ(1280)과 맞춘다. 차내 천장 카메라는 머리가 작아 640 이면 놓친다.
- M1 Ultra 는 --device mps. 오류가 나면 --device cpu (느리지만 결과는 같다).
- 결과: runs/head/<name>/weights/best.pt. 서비스 반영은 README '6. 서비스 반영'.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import BACKEND, CLASS_NAMES, ROOT


def set_class_names(pt: Path) -> None:
    """가중치의 클래스 이름을 head 로 적는다 — 서비스(resolve_target)가 이름을 보고 머리 모드(기준점 = 박스 중심)로 바뀐다."""
    import torch

    ck = torch.load(pt, map_location="cpu", weights_only=False)
    names = dict(enumerate(CLASS_NAMES))
    for k in ("model", "ema"):
        if ck.get(k) is not None:
            ck[k].names = names
    torch.save(ck, pt)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--weights", default=str(BACKEND / "models" / "yolov8n.pt"), help="출발 가중치 (기본 COCO yolov8n)")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--lr0", type=float, default=0.01)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--fraction", type=float, default=1.0, help="학습 데이터 일부만 (시험 실행용)")
    a = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(a.weights)
    model.train(
        data=str(a.data), epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device, workers=a.workers,
        lr0=a.lr0, patience=a.patience, fraction=a.fraction,
        project=str(ROOT / "runs" / "head"), name=a.name, exist_ok=True,
        max_det=1000,                     # 만원 장면 — 기본 300 이면 잘린다
        # 차내 영상 증강: 조도 변화 크게, 좌우 반전, 작은 회전. 상하 반전은 천장 카메라 구도와 맞지 않아 끔
        hsv_v=0.5, hsv_s=0.5, fliplr=0.5, flipud=0.0, degrees=5.0, scale=0.5,
        mosaic=1.0, close_mosaic=10,
        plots=True,
    )
    best = ROOT / "runs" / "head" / a.name / "weights" / "best.pt"
    for pt in best.parent.glob("*.pt"):
        set_class_names(pt)
    print(f"\n완료 → {best}\n다음: python scripts/train/eval_count.py --data {a.data} --weights {best} {BACKEND / 'models' / 'yolov8n.pt'}")


if __name__ == "__main__":
    main()
