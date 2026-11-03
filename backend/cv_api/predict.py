"""검출기 어댑터와 잔여 공간 계산 — BR-CV-28 4필드 계약을 모델이 아닌 서비스가 보장한다.

Detector 인터페이스: detect(img_bgr) -> list[Box(x1,y1,x2,y2,conf)]  (한 사람당 박스 1개 — person 또는 head)
  target = "person"(몸 박스, 기준점 = 발 위치) | "head"(머리 박스, 기준점 = 박스 중심 — 만원 차내에서 발이 가려지므로)
  - YoloV8Detector   : uvicorn 프로세스 안에 가중치 적재 (MaxTheTechy/yolo 의 detector.py 접근법, Ultralytics)
  - OllamaVLDetector : 공유 Ollama 서버의 비전 모델(gemma4:e4b)에 프레임을 보내 사람 박스를 JSON 으로 받음 (qwen3-vl 은 사고 모드 미해제로 출력이 비어 배제)
  - StubDetector     : 테스트용 고정 박스

계산 (research R22 — 인원 ÷ 차량 전체 정원, R20 발자국 면적 방식을 대체):
  신뢰도 ≥ 인원 세기 기준(threshold_policy.count_conf_min) 이고 기준점(몸 = 발 위치, 머리 = 박스 중심)이 ROI 안이면 1명.
  occupied_area_ratio = 인원 ÷ 정원 × 100 (상한 100, 초과는 over_capacity). 정원(제원)이 없으면 산출 불가.
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import cv2
import numpy as np
from shapely.geometry import Point, Polygon

from . import ollama_client
from .settings import Settings, get_settings

Box = Tuple[float, float, float, float, float]


class DetectorNotReady(RuntimeError):
    """G5: 모델 미적재·추론 실패·시간 초과."""


class Detector(Protocol):
    kind: str
    model_name: str
    target: str                          # person | head — compute_occupancy 의 기준점을 정한다

    def load(self) -> float: ...
    def detect(self, img_bgr: np.ndarray, timeout_s: float) -> List[Box]: ...
    def is_loaded(self) -> bool: ...


@dataclass
class DetectorState:
    kind: str = ""
    model: str = ""
    loaded: bool = False
    load_seconds: Optional[float] = None
    warmed_up_at: Optional[str] = None
    last_infer_ms: Optional[int] = None
    note: Optional[str] = None
    contract_ok: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "contract_ok"}


# ------------------------------------------------------------------ YOLOv8 (프로세스 내)
class YoloV8Detector:
    kind = "yolov8"

    def __init__(self, s: Settings):
        self.s = s
        self.model_name = str(s.MODEL_WEIGHTS.name)
        self._model = None
        self.target = "person" if s.MODEL_TARGET == "auto" else s.MODEL_TARGET
        self.class_id = s.MODEL_PERSON_CLASS_ID

    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> float:
        t0 = time.perf_counter()
        from ultralytics import YOLO  # 지연 import — vision extras 미설치 환경에서도 모듈은 import 가능

        if not self.s.MODEL_WEIGHTS.exists():
            raise DetectorNotReady(f"가중치 파일이 없다: {self.s.MODEL_WEIGHTS} — `python -m cv_api.tools.fetch_model` 실행")
        self._model = YOLO(str(self.s.MODEL_WEIGHTS))
        self.target, self.class_id = resolve_target(getattr(self._model, "names", None) or {}, self.s.MODEL_TARGET, self.s.MODEL_PERSON_CLASS_ID)
        return time.perf_counter() - t0

    def detect(self, img_bgr: np.ndarray, timeout_s: float) -> List[Box]:
        if self._model is None:
            raise DetectorNotReady("모델 미적재")
        t0 = time.perf_counter()
        res = self._model.predict(
            img_bgr, classes=[self.class_id], conf=self.s.MODEL_CONF_MIN, imgsz=self.s.MODEL_IMGSZ, device=self.s.MODEL_DEVICE, verbose=False
        )
        if time.perf_counter() - t0 > timeout_s:
            raise DetectorNotReady(f"추론 시간 초과 (> {timeout_s}s)")
        out: List[Box] = []
        for r in res:
            if r.boxes is None:
                continue
            xyxy = r.boxes.xyxy.cpu().numpy()
            conf = r.boxes.conf.cpu().numpy()
            for (x1, y1, x2, y2), c in zip(xyxy, conf):
                out.append((float(x1), float(y1), float(x2), float(y2), float(c)))
        return out


def resolve_target(names: Dict[int, str], wanted: str, fallback_class_id: int) -> Tuple[str, int]:
    """가중치의 클래스 이름으로 검출 대상과 클래스 번호를 정한다. wanted=auto 면 head 가 있으면 head, 아니면 person.
    COCO 가중치(80클래스)는 person=0, 머리 파인튜닝 가중치(scripts/train)는 head=0."""
    by_name = {str(v).lower(): int(k) for k, v in dict(names).items()}
    order = ("head", "person") if wanted == "auto" else (wanted,)
    for name in order:
        if name in by_name:
            return name, by_name[name]
    if wanted == "auto":
        return "person", fallback_class_id
    raise DetectorNotReady(f"가중치에 '{wanted}' 클래스가 없다: {sorted(by_name)} — MODEL_TARGET 확인")


# ------------------------------------------------------------------ Ollama 비전 모델 (공유 서버)
_VL_PROMPT = (
    "You are a person detector for a public-transit crowding service. Detect every visible person in this image. "
    "Return ONLY JSON: {\"width\": W, \"height\": H, \"persons\": [{\"x1\":..,\"y1\":..,\"x2\":..,\"y2\":..,\"conf\":0..1}]} "
    "with pixel coordinates in the ORIGINAL image size. Do not identify anyone. No text outside JSON."
)


class OllamaVLDetector:
    kind = "ollama_vl"
    target = "person"

    def __init__(self, s: Settings):
        self.s = s
        self.model_name = s.OLLAMA_VISION_MODEL
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> float:
        """서버 연결 확인 + 모델 존재 확인 + 미리 올리기(가이드 1.6, 시작 시 1회)."""
        t0 = time.perf_counter()
        ollama_client.health()
        if self.model_name not in ollama_client.installed_models():
            raise DetectorNotReady(f"Ollama 에 모델이 없다: {self.model_name} (가이드 1.5 절차로 추가하거나 OLLAMA_VISION_MODEL 변경)")
        ollama_client.preload(self.model_name, keep_alive=self.s.OLLAMA_KEEP_ALIVE)
        self._loaded = True
        return time.perf_counter() - t0

    def detect(self, img_bgr: np.ndarray, timeout_s: float) -> List[Box]:
        if not self._loaded:
            raise DetectorNotReady("Ollama 비전 모델 미준비")
        h, w = img_bgr.shape[:2]
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise DetectorNotReady("프레임 인코딩 실패")
        t0 = time.perf_counter()
        try:
            text = ollama_client.chat_vision(
                _VL_PROMPT + f" The image is {w}x{h}.", buf.tobytes(), model=self.model_name, json_mode=True,
                timeout=max(timeout_s, self.s.OLLAMA_INFER_TIMEOUT_S),
            )
        except ollama_client.OllamaError as e:
            raise DetectorNotReady(str(e)) from e
        del buf
        return _parse_vl_boxes(text, w, h)


def _parse_vl_boxes(text: str, w: int, h: int) -> List[Box]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise DetectorNotReady("비전 모델 응답에 JSON 이 없다")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise DetectorNotReady(f"비전 모델 JSON 파싱 실패: {e}") from e
    persons = data.get("persons") or data.get("people") or data.get("detections") or []
    rw, rh = data.get("width") or w, data.get("height") or h
    sx, sy = (w / rw if rw else 1.0), (h / rh if rh else 1.0)
    out: List[Box] = []
    for p in persons:
        try:
            x1, y1, x2, y2 = (float(p["x1"]) * sx, float(p["y1"]) * sy, float(p["x2"]) * sx, float(p["y2"]) * sy)
        except (KeyError, TypeError, ValueError):
            continue
        conf = float(p.get("conf", p.get("confidence", 0.7)) or 0.7)
        if x2 > x1 and y2 > y1:
            out.append((max(0, x1), max(0, y1), min(w, x2), min(h, y2), min(1.0, max(0.0, conf))))
    return out


# ------------------------------------------------------------------ Dual Model (v1.3: YOLOv8 Head + YOLO11)
class DualModelDetector:
    """v1.3: YOLOv8 두부 탐지 모델(Model A) + YOLO11 신체/거리 분석 모델(Model B) 융합 엔진."""
    kind = "dual"

    def __init__(self, s: Settings):
        self.s = s
        self.model_name = f"{s.MODEL_WEIGHTS.name}+{s.MODEL_DISTANCE_WEIGHTS.name}"
        self.target = "head"
        self._head_model = None
        self._distance_model = None
        self.head_class_id = 0
        self.person_class_id = 0
        self.last_dual_result: Optional[Dict[str, Any]] = None

    def is_loaded(self) -> bool:
        return self._head_model is not None and self._distance_model is not None

    def load(self) -> float:
        t0 = time.perf_counter()
        from ultralytics import YOLO

        if not self.s.MODEL_WEIGHTS.exists():
            raise DetectorNotReady(f"두부 가중치 파일이 없다: {self.s.MODEL_WEIGHTS}")
        if not self.s.MODEL_DISTANCE_WEIGHTS.exists():
            raise DetectorNotReady(f"거리 분석 가중치 파일이 없다: {self.s.MODEL_DISTANCE_WEIGHTS}")

        self._head_model = YOLO(str(self.s.MODEL_WEIGHTS))
        self._distance_model = YOLO(str(self.s.MODEL_DISTANCE_WEIGHTS))

        # 두부 모델 클래스 식별 (head 또는 0번)
        for k, v in getattr(self._head_model, "names", {}).items():
            if str(v).lower() == "head":
                self.head_class_id = int(k)
                break

        # 신체 거리 모델 클래스 식별 (person 또는 0번)
        for k, v in getattr(self._distance_model, "names", {}).items():
            if str(v).lower() == "person":
                self.person_class_id = int(k)
                break

        return time.perf_counter() - t0

    def compute_center(self, bbox: Sequence[float]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox[:4]
        return round((x1 + x2) / 2.0, 2), round((y1 + y2) / 2.0, 2)

    def calculate_pairwise_distances(self, persons: List[Dict[str, Any]], threshold: float) -> Tuple[List[Dict[str, Any]], float, int, float]:
        n = len(persons)
        pairs: List[Dict[str, Any]] = []
        close_count = 0
        total_dist = 0.0

        for i in range(n):
            for j in range(i + 1, n):
                c1 = persons[i]["center"]
                c2 = persons[j]["center"]
                dist = round(math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2), 2)
                is_close = dist < threshold
                if is_close:
                    close_count += 1
                total_dist += dist
                pairs.append({
                    "pair": [persons[i]["id"], persons[j]["id"]],
                    "pixel_distance": dist,
                    "is_close": is_close,
                })

        total_pairs = len(pairs)
        avg_dist = round(total_dist / total_pairs, 2) if total_pairs > 0 else 0.0
        crowded_ratio = round(close_count / total_pairs, 4) if total_pairs > 0 else 0.0
        return pairs, avg_dist, close_count, crowded_ratio

    def infer_dual(self, img_bgr: np.ndarray, timeout_s: float = 10.0, capacity: Optional[int] = None) -> Dict[str, Any]:
        if not self.is_loaded():
            raise DetectorNotReady("이중 모델 미적재")
        t0 = time.perf_counter()

        # 1. Model A: 두부 탐지 (고해상도 1280)
        head_res = self._head_model.predict(
            img_bgr,
            classes=[self.head_class_id],
            conf=self.s.HEAD_CONF_MIN,
            imgsz=self.s.MODEL_IMGSZ,
            iou=0.45,
            device=self.s.MODEL_DEVICE,
            verbose=False,
        )[0]

        heads: List[Dict[str, Any]] = []
        head_boxes: List[Box] = []
        for idx, box in enumerate(head_res.boxes or []):
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            conf = float(box.conf[0].item())
            heads.append({
                "id": idx,
                "confidence": round(conf, 4),
                "bbox": [round(c, 2) for c in xyxy],
                "center": self.compute_center(xyxy),
            })
            head_boxes.append((float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3]), conf))

        # 2. Model B: YOLO11 전신 검출 -> 거리 행렬
        yolo_res = self._distance_model.predict(
            img_bgr,
            classes=[self.person_class_id],
            conf=self.s.DISTANCE_PERSON_CONF_MIN,
            iou=0.45,
            device=self.s.MODEL_DEVICE,
            verbose=False,
        )[0]

        persons: List[Dict[str, Any]] = []
        for idx, box in enumerate(yolo_res.boxes or []):
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            conf = float(box.conf[0].item())
            persons.append({
                "id": idx,
                "confidence": round(conf, 4),
                "bbox": [round(c, 2) for c in xyxy],
                "center": self.compute_center(xyxy),
            })

        if time.perf_counter() - t0 > timeout_s:
            raise DetectorNotReady(f"추론 시간 초과 (> {timeout_s}s)")

        pairs, avg_dist, close_count, crowded_ratio = self.calculate_pairwise_distances(
            persons, self.s.DISTANCE_THRESHOLD
        )

        cap = capacity if (capacity is not None and capacity > 0) else None
        head_count = len(heads)
        if cap and cap > 0:
            occupancy_ratio = round((head_count / cap) * 100, 2)
            if head_count <= 2 or (occupancy_ratio < 30 and crowded_ratio < 0.2):
                vacancy_status = "EMPTY"
                status_kr = "여유"
            elif occupancy_ratio >= 70 or crowded_ratio >= 0.5:
                vacancy_status = "CROWDED"
                status_kr = "혼잡"
            else:
                vacancy_status = "MODERATE"
                status_kr = "보통"
        else:
            occupancy_ratio = 0.0
            vacancy_status = "UNCERTAIN"
            status_kr = "판독불가"

        payload = {
            "fusion_summary": {
                "head_count": head_count,
                "person_body_count": len(persons),
                "capacity": cap or 0,
                "occupancy_ratio": occupancy_ratio,
                "avg_distance_px": avg_dist,
                "close_pairs_count": close_count,
                "crowded_ratio": crowded_ratio,
                "vacancy_status": vacancy_status,
                "vacancy_status_kr": status_kr,
                "infer_ms": int((time.perf_counter() - t0) * 1000),
            },
            "heads": heads,
            "persons": persons,
            "distance_pairs": pairs,
            "head_boxes": head_boxes,
        }
        self.last_dual_result = payload
        return payload

    def detect(self, img_bgr: np.ndarray, timeout_s: float, capacity: Optional[int] = None) -> List[Box]:
        dual = self.infer_dual(img_bgr, timeout_s=timeout_s, capacity=capacity)
        return dual.get("head_boxes", [])

    def annotate_image(self, orig_img: np.ndarray, payload: Optional[Dict[str, Any]] = None) -> np.ndarray:
        payload = payload or self.last_dual_result
        if not payload:
            return orig_img
        img = orig_img.copy()
        summary = payload.get("fusion_summary", {})

        # 1) YOLO11 전신 박스 (녹색 실선)
        for p in payload.get("persons", []):
            x1, y1, x2, y2 = map(int, p["bbox"])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)

        # 2) YOLO11 중심점 간 근접 거리선 (빨간색 실선)
        person_map = {p["id"]: p for p in payload.get("persons", [])}
        for pair in payload.get("distance_pairs", []):
            if pair.get("is_close"):
                p1_id, p2_id = pair["pair"]
                if p1_id in person_map and p2_id in person_map:
                    c1 = tuple(map(int, person_map[p1_id]["center"]))
                    c2 = tuple(map(int, person_map[p2_id]["center"]))
                    cv2.line(img, c1, c2, (0, 0, 255), 2)

        # 3) Model A 두부 중심점 (파란색 원)
        for h in payload.get("heads", []):
            cx, cy = map(int, h["center"])
            cv2.circle(img, (cx, cy), 4, (255, 0, 0), -1)

        # 4) 상단 이중 모델 종합 대시보드 오버레이
        overlay = f"Heads: {summary.get('head_count', 0)} | Persons: {summary.get('person_body_count', 0)} | Status: {summary.get('vacancy_status_kr', '')} ({summary.get('vacancy_status', '')})"
        cv2.rectangle(img, (0, 0), (img.shape[1], 42), (20, 20, 20), -1)
        cv2.putText(img, overlay, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        return img


# ------------------------------------------------------------------ Stub (테스트)
class StubDetector:
    kind = "stub"
    model_name = "stub"

    def __init__(self, boxes: Optional[List[Box]] = None, target: str = "person"):
        self.boxes = boxes or []
        self.target = target
        self._loaded = False
        self.calls = 0

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> float:
        self._loaded = True
        return 0.0

    def detect(self, img_bgr: np.ndarray, timeout_s: float) -> List[Box]:
        self.calls += 1
        return list(self.boxes)


def build_detector(s: Settings | None = None) -> Detector:
    s = s or get_settings()
    if s.DETECTOR in ("dual", "yolo_dual"):
        return DualModelDetector(s)
    if s.DETECTOR == "yolov8":
        return YoloV8Detector(s)
    if s.DETECTOR == "ollama_vl":
        return OllamaVLDetector(s)
    if s.DETECTOR == "stub":
        return StubDetector()
    raise ValueError(f"알 수 없는 DETECTOR: {s.DETECTOR}")


# ------------------------------------------------------------------ 혼잡도 계산 (R22 — 인원 ÷ 차량 전체 정원)
@dataclass
class Occupancy:
    person_count: int                    # 검출된 사람 전체 (conf ≥ MODEL_CONF_MIN)
    persons_in_roi: int                  # 셈에 든 인원: conf ≥ 인원 세기 기준 이고 기준점(발 위치·머리 중심)이 ROI 안
    occupied_area_ratio: float           # 점유율 % = 인원 ÷ 정원 × 100, 100 상한 (컬럼 이름은 R3 이래 그대로)
    capacity: Optional[int]              # 차량 전체 정원 (제원). 없으면 산출 불가
    over_capacity: bool = False          # 인원 > 정원 → 100% 로 멈추고 표시
    counted_boxes: List[Box] = field(default_factory=list)
    foot_points_in_roi: List[Tuple[float, float]] = field(default_factory=list)   # 셈에 든 기준점 (머리 검출이면 머리 중심)

    @property
    def ratio_computable(self) -> bool:
        return bool(self.capacity and self.capacity > 0)


def polygon_from_text(polygon: str) -> Polygon:
    pts = [tuple(map(float, p.split(","))) for p in polygon.split()]
    return Polygon(pts)


def polygon_to_text(points: Sequence[Sequence[float]]) -> str:
    return " ".join(f"{float(x):g},{float(y):g}" for x, y in points)


def foot_points(boxes: Sequence[Box]) -> List[Tuple[float, float]]:
    return [((b[0] + b[2]) / 2.0, b[3]) for b in boxes]


def center_points(boxes: Sequence[Box]) -> List[Tuple[float, float]]:
    return [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in boxes]


def anchor_points(boxes: Sequence[Box], target: str = "person") -> List[Tuple[float, float]]:
    """ROI 판정 기준점: 몸 박스는 발 위치(아래 중앙), 머리 박스는 박스 중심."""
    return center_points(boxes) if target == "head" else foot_points(boxes)


def compute_occupancy(boxes: Sequence[Box], roi: Polygon, capacity: Optional[int], count_conf_min: float,
                      target: str = "person") -> Occupancy:
    """R22: 인원 세기 기준 이상 · 기준점이 ROI 안인 사람만 센다(몸 = 발 위치, 머리 = 박스 중심). 애매한 검출(기준 미만)은
    장면마다 들어왔다 빠지며 값을 흔들므로 세지 않는다. 점유율 = 인원 ÷ 정원, 정원 초과는 100% 에서 멈추고 over_capacity 로 알린다."""
    counted: List[Box] = []
    inside: List[Tuple[float, float]] = []
    for b, pt in zip(boxes, anchor_points(boxes, target)):
        if b[4] >= count_conf_min and (roi.contains(Point(pt)) or roi.touches(Point(pt))):
            counted.append(b)
            inside.append(pt)
    n = len(counted)
    if capacity and capacity > 0:
        ratio, over = min(100.0, n / capacity * 100.0), n > capacity
    else:
        ratio, over = 0.0, False
    return Occupancy(person_count=len(boxes), persons_in_roi=n, occupied_area_ratio=round(ratio, 2), capacity=capacity,
                     over_capacity=over, counted_boxes=counted, foot_points_in_roi=inside)


def map_level(vacant: float, free_min: float, crowded_max: float) -> str:
    if vacant >= free_min:
        return "free"
    if vacant <= crowded_max:
        return "crowded"
    return "normal"


def make_warmup_frame() -> np.ndarray:
    """더미 프레임: 회색 배경 + 사람 형상 사각형 — 웜업과 4필드 계약 self-check 용."""
    img = np.full((480, 640, 3), 128, dtype=np.uint8)
    cv2.rectangle(img, (280, 120), (360, 400), (40, 40, 40), -1)
    cv2.circle(img, (320, 100), 30, (40, 40, 40), -1)
    return img


def contract_self_check(det: Detector, s: Settings | None = None) -> Dict[str, Any]:
    """웜업 추론 1회로 4필드 계약이 만들어지는지 확인 (BR-CV-28, P1 1.3)."""
    s = s or get_settings()
    img = make_warmup_frame()
    t0 = time.perf_counter()
    boxes = det.detect(img, timeout_s=max(s.INFER_TIMEOUT_S, 30.0))
    ms = int((time.perf_counter() - t0) * 1000)
    roi = Polygon([(0, 0), (640, 0), (640, 480), (0, 480)])
    occ = compute_occupancy(boxes, roi, capacity=10, count_conf_min=s.COUNT_CONF_MIN, target=getattr(det, "target", "person"))
    out = {
        "occupied_area_ratio": occ.occupied_area_ratio,
        "vacant_capacity_ratio": round(100.0 - occ.occupied_area_ratio, 2),
        "crowding_level": map_level(100.0 - occ.occupied_area_ratio, 50, 20),
        "warnings": [],
        "person_count": occ.person_count,
        "infer_ms": ms,
    }
    ok = all(k in out for k in ("occupied_area_ratio", "vacant_capacity_ratio", "crowding_level", "warnings"))
    out["contract_ok"] = ok
    return out
