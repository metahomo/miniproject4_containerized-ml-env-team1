import os
import math
import cv2
import numpy as np
from ultralytics import YOLO

class VacancyDistancePipeline:
    def __init__(self, model_path=None, distance_threshold=150.0, capacity=30):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../.."))
        models_dir = os.environ.get("CV_MODELS_DIR", os.path.join(project_root, "backend", "models"))

        # 1. 두부 탐지 가중치 우선 탐색, 없으면 yolo11n.pt 로 자동 폴백
        head_model_path = os.path.join(models_dir, "head_crowdhuman_n1280.pt")
        default_yolo11 = os.path.join(models_dir, "yolo11n.pt")

        if model_path and os.path.exists(model_path):
            self.model_file = model_path
        elif os.path.exists(head_model_path):
            self.model_file = head_model_path
        elif os.path.exists(default_yolo11):
            self.model_file = default_yolo11
        else:
            raise FileNotFoundError("가중치 파일(yolo11n.pt 또는 head_crowdhuman_n1280.pt)을 찾을 수 없습니다.")

        self.model = YOLO(self.model_file)
        self.distance_threshold = distance_threshold
        self.capacity = capacity  # 차량 또는 공간의 최대 수용 정원

        # 클래스 매핑 (head가 있으면 head=0, 일반 COCO면 person=0)
        names = getattr(self.model, "names", {})
        self.target_class_id = 0
        for cls_id, cls_name in names.items():
            if str(cls_name).lower() in ["head", "person"]:
                self.target_class_id = int(cls_id)
                break

    def compute_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return round((x1 + x2) / 2.0, 2), round((y1 + y2) / 2.0, 2)

    def calculate_metrics(self, objects):
        n = len(objects)
        pairs = []
        close_pairs_count = 0
        total_dist = 0.0

        for i in range(n):
            for j in range(i + 1, n):
                c1 = objects[i]["center"]
                c2 = objects[j]["center"]
                dist = round(math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2), 2)
                is_close = dist < self.distance_threshold
                if is_close:
                    close_pairs_count += 1
                total_dist += dist

                pairs.append({
                    "pair": [objects[i]["id"], objects[j]["id"]],
                    "pixel_distance": dist,
                    "is_close": is_close
                })

        total_pairs = len(pairs)
        avg_dist = round(total_dist / total_pairs, 2) if total_pairs > 0 else 0.0
        crowded_ratio = round(close_pairs_count / total_pairs, 4) if total_pairs > 0 else 0.0
        occupancy_ratio = round((n / self.capacity) * 100, 2)

        # 여유 공간 상태 판정
        if n <= 2 or (crowded_ratio < 0.2 and occupancy_ratio < 30):
            vacancy_status = "EMPTY"        # 여유/쾌적
            status_kr = "여유"
        elif crowded_ratio >= 0.5 or occupancy_ratio >= 70:
            vacancy_status = "CROWDED"      # 혼잡/만석
            status_kr = "혼잡"
        else:
            vacancy_status = "MODERATE"     # 보통
            status_kr = "보통"

        return pairs, {
            "head_count": n,
            "capacity": self.capacity,
            "occupancy_ratio": occupancy_ratio,
            "avg_distance_px": avg_dist,
            "close_pairs_count": close_pairs_count,
            "crowded_ratio": crowded_ratio,
            "vacancy_status": vacancy_status,
            "vacancy_status_kr": status_kr
        }

    def infer(self, image_input, conf=0.2):
        results = self.model.predict(
            source=image_input,
            classes=[self.target_class_id],
            conf=conf,
            verbose=False
        )
        result = results[0]

        objects = []
        for idx, box in enumerate(result.boxes):
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            conf_val = round(float(box.conf[0].item()), 4)
            cx, cy = self.compute_center(xyxy)
            objects.append({
                "id": idx,
                "confidence": conf_val,
                "bbox": [round(c, 2) for c in xyxy],
                "center": [cx, cy]
            })

        distance_pairs, space_metrics = self.calculate_metrics(objects)

        payload = {
            "model_used": os.path.basename(self.model_file),
            "space_analysis": space_metrics,
            "detected_objects": objects,
            "distance_pairs": distance_pairs
        }
        return payload, result.orig_img

    def visualize(self, orig_img, payload, save_path):
        img = orig_img.copy()
        obj_map = {obj["id"]: obj for obj in payload["detected_objects"]}
        metrics = payload["space_analysis"]

        # 바운딩 박스 및 중심점
        for obj in payload["detected_objects"]:
            x1, y1, x2, y2 = map(int, obj["bbox"])
            cx, cy = map(int, obj["center"])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(img, (cx, cy), 4, (0, 0, 255), -1)

        # 근접 거리 선 시각화
        for pair in payload["distance_pairs"]:
            if pair["is_close"]:
                id1, id2 = pair["pair"]
                c1 = tuple(map(int, obj_map[id1]["center"]))
                c2 = tuple(map(int, obj_map[id2]["center"]))
                cv2.line(img, c1, c2, (0, 0, 255), 2)

        # 상단 대시보드 오버레이
        overlay_text = f"Count: {metrics['head_count']}/{metrics['capacity']} | Status: {metrics['vacancy_status_kr']} ({metrics['vacancy_status']}) | Dense Ratio: {metrics['crowded_ratio']*100:.1f}%"
        cv2.rectangle(img, (0, 0), (img.shape[1], 40), (0, 0, 0), -1)
        cv2.putText(img, overlay_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, img)