"""scripts/train 공통 — 경로·YOLO 라벨 입출력·그룹 키.

데이터 폴더 규칙 (YOLO 형식, 클래스 1개 head=0):
  datasets/<이름>/images/<split>/<파일>.jpg
  datasets/<이름>/labels/<split>/<파일>.txt   # 줄마다 "0 cx cy w h" (0~1 정규화)
파일 이름 규칙: <출처>__<카메라>__<날짜>__<순번>.jpg — 앞 세 칸(출처·카메라·날짜)이 같은 프레임은 같은 그룹으로 보고
학습/검증/시험에 나눠 넣지 않는다(연속 프레임이 양쪽에 들어가면 점수가 부풀려진다).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATASETS = ROOT / "datasets"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_NAMES = ["head"]

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

XYXY = Tuple[float, float, float, float]


def list_images(folder: Path) -> List[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMG_EXTS)


def label_path_for(img: Path) -> Path:
    """.../images/<split>/a.jpg → .../labels/<split>/a.txt (ultralytics 규칙)."""
    parts = list(img.parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "images":
            parts[i] = "labels"
            break
    return Path(*parts).with_suffix(".txt")


def to_yolo_line(box: XYXY, w: int, h: int, cls: int = 0) -> str | None:
    x1, y1, x2, y2 = max(0.0, box[0]), max(0.0, box[1]), min(float(w), box[2]), min(float(h), box[3])
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return f"{cls} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}"


def write_labels(path: Path, boxes: Iterable[XYXY], w: int, h: int) -> int:
    lines = [ln for ln in (to_yolo_line(b, w, h) for b in boxes) if ln]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


def read_labels(path: Path, w: int = 1, h: int = 1) -> List[XYXY]:
    """YOLO 라벨 → 픽셀 xyxy (w·h 를 안 주면 0~1 좌표)."""
    if not path.exists():
        return []
    out: List[XYXY] = []
    for ln in path.read_text().split("\n"):
        f = ln.split()
        if len(f) < 5:
            continue
        cx, cy, bw, bh = (float(v) for v in f[1:5])
        out.append(((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
    return out


def group_key(name: str) -> str:
    parts = Path(name).stem.split("__")
    return "__".join(parts[:3]) if len(parts) >= 4 else Path(name).stem


def write_data_yaml(ds: Path, splits: Sequence[str] = ("train", "val", "test")) -> Path:
    lines = [f"path: {ds.resolve()}"] + [f"{s}: images/{s}" for s in splits if (ds / "images" / s).exists()]
    lines += ["names:"] + [f"  {i}: {n}" for i, n in enumerate(CLASS_NAMES)]
    p = ds / "data.yaml"
    p.write_text("\n".join(lines) + "\n")
    return p
