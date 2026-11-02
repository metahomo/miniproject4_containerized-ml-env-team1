"""6단계 — 인원 수로 평가하고 인원 세기 기준(COUNT_CONF_MIN)을 다시 정한다. mAP 가 아니라 서비스가 내는 숫자로 본다.

  python scripts/train/eval_count.py --data datasets/transit_head/data.yaml --split test \
      --weights runs/head/transit/weights/best.pt backend/models/yolov8n.pt --capacity 80

- 여러 가중치를 한 번에 비교한다. COCO 가중치는 person(발 위치), 머리 가중치는 head(박스 중심)로 서비스와 같은 규칙
  (cv_api.predict.resolve_target · compute_occupancy)으로 센다. 정답 = 라벨 파일의 머리 수.
- 기준값 0.20~0.70 을 훑어 프레임당 인원 오차(MAE)가 가장 작은 값을 추천한다.
- --capacity 를 주면 서비스 목표 SC-01(잔여 비율 ±10%p 이내 일치 비율, 목표 85%)도 계산한다.
- --roi "x,y x,y ..." (0~1 비율 좌표)로 ROI 를 줄 수 있다. 없으면 화면 전체.
- 결과는 표준 출력 + --out JSON.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import yaml
from shapely.geometry import Polygon

from common import label_path_for, list_images, read_labels

THRESHOLDS = [round(0.20 + 0.05 * i, 2) for i in range(11)]


def gt_count(img: Path, roi_px: Polygon, w: int, h: int) -> int:
    from cv_api.predict import compute_occupancy

    boxes = [(*b, 1.0) for b in read_labels(label_path_for(img), w, h)]
    return compute_occupancy(boxes, roi_px, None, 0.0, target="head").persons_in_roi


def evaluate(weights: str, imgs: List[Path], roi_rel, imgsz: int, device: str, capacity: int | None) -> Dict:
    from ultralytics import YOLO
    from cv_api.predict import compute_occupancy, resolve_target

    model = YOLO(weights)
    target, cls = resolve_target(model.names, "auto", 0)
    gts: List[int] = []
    preds: Dict[float, List[int]] = {t: [] for t in THRESHOLDS}
    ms: List[float] = []
    for img in imgs:
        r = model.predict(str(img), classes=[cls], conf=min(THRESHOLDS), imgsz=imgsz, device=device, verbose=False, max_det=1000)[0]
        h, w = r.orig_shape
        roi = Polygon([(x * w, y * h) for x, y in roi_rel])
        gts.append(gt_count(img, roi, w, h))
        boxes = [(*map(float, b), float(c)) for b, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy())]
        for t in THRESHOLDS:
            preds[t].append(compute_occupancy(boxes, roi, None, t, target=target).persons_in_roi)
        ms.append(sum(r.speed.values()))
    g = np.array(gts, dtype=float)
    rows = []
    for t in THRESHOLDS:
        p = np.array(preds[t], dtype=float)
        row = {"thr": t, "mae": float(np.abs(p - g).mean()), "bias": float((p - g).mean()),
               "mape": float((np.abs(p - g) / np.maximum(g, 1)).mean() * 100)}
        if capacity:
            row["sc01"] = float((np.abs(np.minimum(p, capacity) - np.minimum(g, capacity)) / capacity * 100 <= 10).mean() * 100)
        rows.append(row)
    best = min(rows, key=lambda r: r["mae"])
    return {"weights": weights, "target": target, "frames": len(imgs), "gt_mean": float(g.mean()),
            "ms_per_frame": float(np.mean(ms)), "rows": rows, "best": best}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--weights", nargs="+", required=True)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--capacity", type=int)
    ap.add_argument("--roi", default="0,0 1,0 1,1 0,1")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    cfg = yaml.safe_load(a.data.read_text())
    base = Path(cfg.get("path") or a.data.parent)
    folder = base / cfg.get(a.split, f"images/{a.split}")
    imgs = list_images(folder)[: a.limit or None]
    if not imgs:
        raise SystemExit(f"이미지가 없다: {folder}")
    roi_rel = [tuple(map(float, p.split(","))) for p in a.roi.split()]

    results = [evaluate(w, imgs, roi_rel, a.imgsz, a.device, a.capacity) for w in a.weights]
    print(f"\n평가: {folder} — {len(imgs)}장, 정답 평균 {results[0]['gt_mean']:.1f}명/장\n")
    for res in results:
        print(f"■ {res['weights']}  (대상 {res['target']}, {res['ms_per_frame']:.0f} ms/장)")
        print("   기준값   MAE    편향    MAPE%" + ("   SC-01%" if a.capacity else ""))
        for r in res["rows"]:
            mark = " ◀ 추천" if r is res["best"] else ""
            sc = f"  {r['sc01']:6.1f}" if a.capacity else ""
            print(f"   {r['thr']:.2f}  {r['mae']:6.2f}  {r['bias']:+6.2f}  {r['mape']:6.1f}{sc}{mark}")
        print()
    b = min(results, key=lambda r: r["best"]["mae"])
    print(f"가장 좋은 모델: {b['weights']} · COUNT_CONF_MIN={b['best']['thr']:.2f} · MAE {b['best']['mae']:.2f}명 (편향 {b['best']['bias']:+.2f})")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"→ {a.out}")


if __name__ == "__main__":
    main()
