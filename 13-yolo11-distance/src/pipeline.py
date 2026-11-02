import os
import math
import cv2
import numpy as np
from ultralytics import YOLO

class DistancePipeline:
    def __init__(self, model_path=None, distance_threshold=150.0):
        if model_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, "../.."))
            model_path = os.path.join(project_root, "backend", "models", "yolo11n.pt")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {model_path}")

        self.model = YOLO(model_path)
        self.distance_threshold = distance_threshold

    def compute_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return round((x1 + x2) / 2.0, 2), round((y1 + y2) / 2.0, 2)

    def calculate_pairwise_distances(self, objects):
        pairs = []
        n = len(objects)
        for i in range(n):
            for j in range(i + 1, n):
                c1 = objects[i]["center"]
                c2 = objects[j]["center"]
                dist = round(math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2), 2)
                pairs.append({
                    "pair": [objects[i]["id"], objects[j]["id"]],
                    "pixel_distance": dist,
                    "is_close": dist < self.distance_threshold
                })
        return pairs

    def infer(self, image_input, conf=0.25):
        results = self.model.predict(source=image_input, conf=conf, verbose=False)
        result = results[0]

        objects = []
        for idx, box in enumerate(result.boxes):
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            cls_id = int(box.cls[0].item())
            conf_val = round(float(box.conf[0].item()), 4)
            label = self.model.names[cls_id]

            cx, cy = self.compute_center(xyxy)
            objects.append({
                "id": idx,
                "class_name": label,
                "confidence": conf_val,
                "bbox": [round(coord, 2) for coord in xyxy],
                "center": [cx, cy]
            })

        pairs = self.calculate_pairwise_distances(objects)

        output_payload = {
            "model_version": "YOLO11n",
            "total_objects": len(objects),
            "objects": objects,
            "distance_pairs": pairs
        }
        return output_payload, result.orig_img

    def visualize(self, orig_img, output_payload, save_path):
        img = orig_img.copy()
        obj_map = {obj["id"]: obj for obj in output_payload["objects"]}

        for obj in output_payload["objects"]:
            x1, y1, x2, y2 = map(int, obj["bbox"])
            cx, cy = map(int, obj["center"])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(img, (cx, cy), 4, (0, 0, 255), -1)
            cv2.putText(img, f"ID:{obj['id']} {obj['class_name']}", (x1, max(y1 - 6, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        for pair in output_payload["distance_pairs"]:
            if pair["is_close"]:
                id1, id2 = pair["pair"]
                c1 = tuple(map(int, obj_map[id1]["center"]))
                c2 = tuple(map(int, obj_map[id2]["center"]))
                cv2.line(img, c1, c2, (0, 0, 255), 2)
                mid_x = int((c1[0] + c2[0]) / 2)
                mid_y = int((c1[1] + c2[1]) / 2)
                cv2.putText(img, f"{pair['pixel_distance']}px", (mid_x, mid_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, img)
