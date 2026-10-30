"""모델 가져오기 — P1 1.1, BR-CV-31. Clarifications Q12: https://github.com/MaxTheTechy/yolo (YOLOv8n).

가중치 yolov8n.pt 는 Ultralytics 배포본과 동일하므로 저장소 clone 없이 Ultralytics 가 받는다(저장소 코드는 가져오지 않는다 — R3).
model_package.json 에 저장소·커밋(확인 가능하면)·가중치·라이선스(없음)·계약 확인 결과(adapter)를 기록한다.

사용: python -m cv_api.tools.fetch_model [--weights yolov8n.pt] [--commit <hash>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..settings import BACKEND_DIR, get_settings


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=s.MODEL_WEIGHTS.name)
    ap.add_argument("--repo", default=s.MODEL_REPO)
    ap.add_argument("--commit", default="unknown")
    a = ap.parse_args()

    models_dir = BACKEND_DIR / "models"
    models_dir.mkdir(exist_ok=True)
    target = models_dir / a.weights
    if not target.exists():
        from ultralytics import YOLO

        m = YOLO(a.weights)  # 없으면 Ultralytics 가 내려받는다
        src = Path(m.ckpt_path) if getattr(m, "ckpt_path", None) else Path(a.weights)
        if src.exists() and src.resolve() != target.resolve():
            shutil.copy(src, target)
        elif Path(a.weights).exists() and Path(a.weights).resolve() != target.resolve():
            shutil.move(a.weights, target)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    rec = {
        "repo_url": a.repo,
        "commit_hash": a.commit if a.commit != "unknown" else f"weights-sha256:{sha}",
        "weights_file": target.name,
        "license": None,   # 저장소에 라이선스 파일 없음 (research R3). 가중치는 Ultralytics AGPL-3.0 — 배포 전 확인
        "required_versions": "ultralytics>=8.2, torch>=2.1",
        "contract_check_result": "adapter",
        "detector_kind": "yolov8",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (models_dir / "model_package.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
