"""2026-09-30 — 모델 판본 기록은 실제로 적재한 가중치를 따른다 (가중치를 바꿔도 model_package.json 의 yolov8n 으로 기록되던 결함)."""
import json

from cv_api.services import ops
from cv_api.settings import Settings


def test_sidecar_then_base_then_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "BACKEND_DIR", tmp_path)
    (tmp_path / "models").mkdir()
    base = {"repo_url": "r", "commit_hash": "weights-sha256:base", "weights_file": "yolov8n.pt", "license": None}
    (tmp_path / "models" / "model_package.json").write_text(json.dumps(base))
    for name in ("yolov8n.pt", "head.pt", "other.pt"):
        (tmp_path / "models" / name).write_bytes(name.encode())
    (tmp_path / "models" / "head.json").write_text(json.dumps({**base, "commit_hash": "weights-sha256:head", "weights_file": "head.pt", "license": "L"}))

    rec = lambda w: ops._weights_record(Settings(MODEL_WEIGHTS=tmp_path / "models" / w))   # noqa: E731
    assert rec("yolov8n.pt")["commit_hash"] == "weights-sha256:base"          # 기본 파일 = model_package.json
    assert rec("head.pt")["commit_hash"] == "weights-sha256:head" and rec("head.pt")["license"] == "L"   # 설명 파일
    other = rec("other.pt")
    assert other["weights_file"] == "other.pt" and other["commit_hash"].startswith("weights-sha256:") and other["commit_hash"] != "weights-sha256:base"


def test_record_has_only_table_columns(tmp_path, monkeypatch):
    class Det:
        kind = "yolov8"
    monkeypatch.setattr(ops, "_weights_record", lambda s: {"repo_url": "r", "commit_hash": "c", "weights_file": "w", "training": {"x": 1}})
    r = ops._model_package_record(Settings(), Det())
    assert "training" not in r and r["weights_file"] == "w" and r["detector_kind"] == "yolov8"
