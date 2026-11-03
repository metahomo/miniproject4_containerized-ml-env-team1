import os
import math
import cv2
import numpy as np
import torch
from ultralytics import YOLO

class DualModelVacancyPipeline:
    def __init__(self, distance_threshold=150.0, capacity=30, device=None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../.."))

        # 1. 환경 변수(CV_MODELS_DIR) 우선 참조, 미지정 시 기본 경로 폴백
        models_dir = os.environ.get("CV_MODELS_DIR", os.path.join(project_root, "backend", "models"))
        self.head_model_path = os.path.join(models_dir, "head_crowdhuman_n1280.pt")
        self.yolo11_model_path = os.path.join(models_dir, "yolo11n.pt")

        if not os.path.exists(self.head_model_path):
            raise FileNotFoundError(f"두부 모델 미발견: {self.head_model_path}")
        if not os.path.exists(self.yolo11_model_path):
            raise FileNotFoundError(f"YOLO11 모델 미발견: {self.yolo11_model_path}")

        # 2. 실행 디바이스 자동 선택 (명시적 인자가 없으면 GPU 가용 여부 자동 판별)
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")

        # 3. 두 모델 로드
        self.head_model = YOLO(self.head_model_path)
        self.distance_model = YOLO(self.yolo11_model_path)

        self.distance_threshold = distance_threshold
        self.capacity = capacity

        # 클래스 ID 자동 매핑 (COCO 또는 차내 특화 커스텀 모델 자동 호환)
        self.head_class_id = 0
        for k, v in getattr(self.head_model, "names", {}).items():
            if v == "head":
                self.head_class_id = k
                break

        self.person_class_id = 0
        for k, v in getattr(self.distance_model, "names", {}).items():
            if v == "person":
                self.person_class_id = k
                break

    def compute_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return round((x1 + x2) / 2.0, 2), round((y1 + y2) / 2.0, 2)

    def calculate_pairwise_distances(self, persons):
        n = len(persons)
        pairs = []
        close_count = 0
        total_dist = 0.0

        for i in range(n):
            for j in range(i + 1, n):
                c1 = persons[i]["center"]
                c2 = persons[j]["center"]
                dist = round(math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2), 2)
                is_close = dist < self.distance_threshold
                if is_close:
                    close_count += 1
                total_dist += dist

                pairs.append({
                    "pair": [persons[i]["id"], persons[j]["id"]],
                    "pixel_distance": dist,
                    "is_close": is_close
                })

        total_pairs = len(pairs)
        avg_dist = round(total_dist / total_pairs, 2) if total_pairs > 0 else 0.0
        crowded_ratio = round(close_count / total_pairs, 4) if total_pairs > 0 else 0.0
        return pairs, avg_dist, close_count, crowded_ratio

    def infer(self, image_bgr, head_conf=0.12, person_conf=0.15, head_imgsz=1280, iou=0.45):
        # 1. Model A (YOLOv8 Head): 두부/인원 탐지 (고해상도 1280 규격)
        head_res = self.head_model.predict(
            image_bgr,
            classes=[self.head_class_id],
            conf=head_conf,
            imgsz=head_imgsz,
            iou=iou,
            device=self.device,
            verbose=False
        )[0]
        heads = []
        for idx, box in enumerate(head_res.boxes):
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            heads.append({
                "id": idx,
                "confidence": round(float(box.conf[0].item()), 4),
                "bbox": [round(c, 2) for c in xyxy],
                "center": self.compute_center(xyxy)
            })
        head_count = len(heads)

        # 2. Model B (YOLO11): 전신 바운딩 박스 탐지 -> 거리 행렬 계산
        yolo_res = self.distance_model.predict(
            image_bgr,
            classes=[self.person_class_id],
            conf=person_conf,
            iou=iou,
            device=self.device,
            verbose=False
        )[0]
        persons = []
        for idx, box in enumerate(yolo_res.boxes):
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            persons.append({
                "id": idx,
                "confidence": round(float(box.conf[0].item()), 4),
                "bbox": [round(c, 2) for c in xyxy],
                "center": self.compute_center(xyxy)
            })

        pairs, avg_dist, close_count, crowded_ratio = self.calculate_pairwise_distances(persons)

        # 3. 데이터 융합 (Fusion) 판정
        occupancy_ratio = round((head_count / self.capacity) * 100, 2)
        if head_count <= 2 or (occupancy_ratio < 30 and crowded_ratio < 0.2):
            vacancy_status = "EMPTY"
            status_kr = "여유"
        elif occupancy_ratio >= 70 or crowded_ratio >= 0.5:
            vacancy_status = "CROWDED"
            status_kr = "혼잡"
        else:
            vacancy_status = "MODERATE"
            status_kr = "보통"

        payload = {
            "fusion_summary": {
                "head_count": head_count,
                "person_body_count": len(persons),
                "capacity": self.capacity,
                "occupancy_ratio": occupancy_ratio,
                "avg_distance_px": avg_dist,
                "close_pairs_count": close_count,
                "crowded_ratio": crowded_ratio,
                "vacancy_status": vacancy_status,
                "vacancy_status_kr": status_kr
            },
            "heads": heads,
            "persons": persons,
            "distance_pairs": pairs
        }
        return payload, image_bgr

    def visualize(self, orig_img, payload, save_path):
        img = orig_img.copy()
        summary = payload["fusion_summary"]

        # 1) YOLO11 전신 박스 (녹색 실선)
        for p in payload["persons"]:
            x1, y1, x2, y2 = map(int, p["bbox"])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)

        # 2) YOLO11 중심점 간 근접 거리선 (빨간색 실선)
        person_map = {p["id"]: p for p in payload["persons"]}
        for pair in payload["distance_pairs"]:
            if pair["is_close"]:
                c1 = tuple(map(int, person_map[pair["pair"][0]]["center"]))
                c2 = tuple(map(int, person_map[pair["pair"][1]]["center"]))
                cv2.line(img, c1, c2, (0, 0, 255), 2)

        # 3) Model A 두부 중심점 (파란색 원)
        for h in payload["heads"]:
            cx, cy = map(int, h["center"])
            cv2.circle(img, (cx, cy), 4, (255, 0, 0), -1)

        # 4) 상단 이중 모델 종합 대시보드 오버레이
        overlay = f"Heads: {summary['head_count']} | Persons: {summary['person_body_count']} | Status: {summary['vacancy_status_kr']} ({summary['vacancy_status']})"
        cv2.rectangle(img, (0, 0), (img.shape[1], 42), (20, 20, 20), -1)
        cv2.putText(img, overlay, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, img)
