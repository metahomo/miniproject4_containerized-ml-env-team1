"""3단계 — 머리 모델로 자동 라벨을 먼저 달고, 사람은 CVAT 에서 고치기만 한다.

  python scripts/train/autolabel.py --weights runs/head/crowdhuman/weights/best.pt \
      --images datasets/transit_head/images/pool --conf 0.3 --cvat-zip datasets/transit_head/pool_cvat.zip

- 라벨은 datasets/.../labels/pool/<이름>.txt 에 쓴다. 이미 있는 라벨(사람이 고친 것)은 --overwrite 없이는 건드리지 않는다.
- --cvat-zip: CVAT «YOLO 1.1» 가져오기용 zip. CVAT 에서 작업(task)을 만들 때 같은 이미지를 올리고 Upload annotations 로 넣는다.
  고친 뒤 «YOLO 1.1» 로 내보내 압축의 obj_train_data/*.txt 를 labels/pool/ 에 덮어쓴다.
- 라벨 규칙 (README 의 '라벨링 규칙'): 일부라도 보이는 머리는 표시, 창밖·유리 반사·광고 속 사람은 제외.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from common import CLASS_NAMES, label_path_for, list_images, to_yolo_line


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--conf", type=float, default=0.3, help="자동 라벨 신뢰도 하한 (낮추면 빠진 머리↓·지울 박스↑)")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--cvat-zip", type=Path)
    a = ap.parse_args()

    from ultralytics import YOLO
    from cv_api.predict import resolve_target

    model = YOLO(str(a.weights))
    target, cls = resolve_target(model.names, "auto", 0)
    if target != "head":
        print(f"[주의] {a.weights.name} 는 머리 모델이 아니다({target}). 몸 박스가 라벨로 들어간다.")
    imgs = list_images(a.images)
    written = skipped = boxes = 0
    for img in imgs:
        lp = label_path_for(img)
        if lp.exists() and not a.overwrite:
            skipped += 1
            continue
        r = model.predict(str(img), classes=[cls], conf=a.conf, imgsz=a.imgsz, device=a.device, verbose=False)[0]
        h, w = r.orig_shape
        lines = [ln for ln in (to_yolo_line(tuple(map(float, b)), w, h) for b in r.boxes.xyxy.cpu().numpy()) if ln]
        lp.parent.mkdir(parents=True, exist_ok=True)
        lp.write_text("\n".join(lines) + ("\n" if lines else ""))
        written += 1
        boxes += len(lines)
    print(f"자동 라벨 {written}장(머리 {boxes}개), 기존 라벨 유지 {skipped}장")

    if a.cvat_zip:
        with zipfile.ZipFile(a.cvat_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("obj.names", "\n".join(CLASS_NAMES) + "\n")
            z.writestr("obj.data", f"classes = {len(CLASS_NAMES)}\nnames = obj.names\ntrain = train.txt\n")
            z.writestr("train.txt", "\n".join(f"obj_train_data/{i.name}" for i in imgs) + "\n")
            for img in imgs:
                lp = label_path_for(img)
                z.writestr(f"obj_train_data/{img.stem}.txt", lp.read_text() if lp.exists() else "")
        print(f"CVAT YOLO 1.1 → {a.cvat_zip}")


if __name__ == "__main__":
    main()
