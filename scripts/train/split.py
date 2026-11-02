"""4단계 — 라벨을 마친 pool 을 학습/검증/시험으로 나눈다. 같은 그룹(출처·카메라·날짜)은 한 쪽에만 들어간다.

  python scripts/train/split.py datasets/transit_head --ratios 0.7 0.15 0.15

- images/pool + labels/pool → images/{train,val,test} + labels/{...} 로 옮기고 data.yaml 을 쓴다.
- 라벨 파일이 없는 이미지(아직 안 고친 것)는 pool 에 남긴다. 빈 라벨 파일(사람 없음)은 정상 — 오검출을 줄여 준다.
- 그룹 배정은 그룹 이름의 해시로 정해져 다시 돌려도 같다. 시험 세트에는 학습에 없는 카메라가 들어가야 실제 성능이 보인다.
"""
from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from common import group_key, label_path_for, list_images, write_data_yaml

SPLITS = ("train", "val", "test")


def assign(key: str, ratios) -> str:
    u = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    acc = 0.0
    for name, r in zip(SPLITS, ratios):
        acc += r
        if u < acc:
            return name
    return SPLITS[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--ratios", type=float, nargs=3, default=(0.7, 0.15, 0.15))
    ap.add_argument("--pool", default="pool")
    a = ap.parse_args()

    groups = defaultdict(list)
    for img in list_images(a.dataset / "images" / a.pool):
        if label_path_for(img).exists():
            groups[group_key(img.name)].append(img)
    if not groups:
        raise SystemExit(f"라벨이 있는 이미지가 없다: {a.dataset / 'images' / a.pool}")
    moved = defaultdict(int)
    gcount = defaultdict(int)
    for key, imgs in groups.items():
        sp = assign(key, a.ratios)
        gcount[sp] += 1
        for img in imgs:
            lp = label_path_for(img)
            (a.dataset / "images" / sp).mkdir(parents=True, exist_ok=True)
            (a.dataset / "labels" / sp).mkdir(parents=True, exist_ok=True)
            img.rename(a.dataset / "images" / sp / img.name)
            lp.rename(a.dataset / "labels" / sp / lp.name)
            moved[sp] += 1
    y = write_data_yaml(a.dataset)
    for sp in SPLITS:
        print(f"{sp:5s}: {moved[sp]:5d}장 / 그룹 {gcount[sp]}")
    if len(groups) < 6:
        print("[주의] 그룹이 6개 미만 — 카메라·날짜를 늘려야 검증·시험 세트가 의미 있다.")
    print(f"→ {y}")


if __name__ == "__main__":
    main()
