"""2단계(보조) — 공개 머리 데이터셋을 YOLO 형식(head=0)으로 바꾼다. 우리 차내 데이터 전에 1차 학습용.

  # CrowdHuman (머리 박스 hbox 사용, 라이선스 CC BY-NC 4.0 — 비상업 연구용)
  python scripts/train/convert_public.py crowdhuman --odgt datasets/raw/crowdhuman/annotation_val.odgt \
      --images datasets/raw/crowdhuman/Images --out datasets/crowdhuman_head --split val

  # SCUT-HEAD 등 Pascal VOC xml (객체 이름과 관계없이 모든 박스를 머리로)
  python scripts/train/convert_public.py voc --xml-dir .../Annotations --images .../JPEGImages \
      --out datasets/scut_head --split train

이미지는 복사하지 않고 심볼릭 링크를 만든다(--copy 로 복사). 파일 이름 앞에 출처를 붙여(<출처>__<원래이름>) 그룹 키가 겹치지 않게 한다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, List, Tuple

import cv2

from common import XYXY, write_data_yaml, write_labels


def crowdhuman(odgt: Path, images: Path) -> Iterator[Tuple[Path, List[XYXY]]]:
    for line in odgt.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        img = images / f"{rec['ID']}.jpg"
        boxes: List[XYXY] = []
        for g in rec.get("gtboxes", []):
            if g.get("tag") != "person" or "hbox" not in g:
                continue          # mask = 사람 모양 광고·그림 등 무시 영역
            if (g.get("head_attr") or {}).get("ignore") == 1 or (g.get("extra") or {}).get("ignore") == 1:
                continue
            x, y, w, h = g["hbox"]
            boxes.append((x, y, x + w, y + h))
        yield img, boxes


def voc(xml_dir: Path, images: Path) -> Iterator[Tuple[Path, List[XYXY]]]:
    for xp in sorted(xml_dir.glob("*.xml")):
        root = ET.parse(xp).getroot()
        fname = root.findtext("filename") or f"{xp.stem}.jpg"
        boxes: List[XYXY] = []
        for o in root.iter("object"):
            bb = o.find("bndbox")
            if bb is None:
                continue
            boxes.append(tuple(float(bb.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")))
        yield images / fname, boxes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["crowdhuman", "voc"])
    ap.add_argument("--odgt", type=Path)
    ap.add_argument("--xml-dir", type=Path)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", default="train")
    ap.add_argument("--prefix", help="파일 이름 앞 출처 (기본 kind)")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N장만 (시험용)")
    ap.add_argument("--copy", action="store_true")
    a = ap.parse_args()

    it = crowdhuman(a.odgt, a.images) if a.kind == "crowdhuman" else voc(a.xml_dir, a.images)
    prefix = a.prefix or a.kind
    img_dir = a.out / "images" / a.split
    lab_dir = a.out / "labels" / a.split
    img_dir.mkdir(parents=True, exist_ok=True)
    n_img = n_box = missing = 0
    for src, boxes in it:
        if a.limit and n_img >= a.limit:
            break
        if not src.exists():
            missing += 1
            continue
        im = cv2.imread(str(src))
        if im is None:
            missing += 1
            continue
        h, w = im.shape[:2]
        dst = img_dir / f"{prefix}__{src.name}"
        if not dst.exists():
            shutil.copy2(src, dst) if a.copy else dst.symlink_to(src.resolve())
        n_box += write_labels(lab_dir / f"{dst.stem}.txt", boxes, w, h)
        n_img += 1
    write_data_yaml(a.out)
    print(f"{a.kind} → {a.out} [{a.split}]: 이미지 {n_img}장, 머리 {n_box}개 (장당 {n_box / max(1, n_img):.1f}), 없음 {missing}")


if __name__ == "__main__":
    main()
