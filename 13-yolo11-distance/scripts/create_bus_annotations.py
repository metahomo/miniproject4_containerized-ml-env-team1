import os
import cv2
import numpy as np
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SUMTONG_ROOT = os.path.abspath(os.path.join(PROJECT_DIR, ".."))

def generate_base_labels():
    raw_dir = os.path.join(PROJECT_DIR, "data", "raw_bus_annotated")
    os.makedirs(raw_dir, exist_ok=True)

    head_model_p = os.path.join(SUMTONG_ROOT, "backend", "models", "head_crowdhuman_n1280.pt")
    body_model_p = os.path.join(SUMTONG_ROOT, "backend", "models", "yolo11n.pt")

    model_head = YOLO(head_model_p)
    model_body = YOLO(body_model_p)

    samples = [
        ("bus_full.jpg", os.path.join(SUMTONG_ROOT, "backend", "samples", "bus_full.jpg")),
        ("bus_empty.jpg", os.path.join(SUMTONG_ROOT, "backend", "samples", "bus_empty.jpg")),
        ("bus_blur.jpg", os.path.join(SUMTONG_ROOT, "backend", "samples", "bus_blur.jpg")),
        ("bench_frame.jpg", os.path.join(SUMTONG_ROOT, "backend", "samples", "bench_frame.jpg"))
    ]

    for name, path in samples:
        if not os.path.exists(path):
            continue
        img = cv2.imread(path)
        h, w = img.shape[:2]

        # 1. 두부 추출 (클래스 0)
        res_head = model_head.predict(img, imgsz=1280, conf=0.08, verbose=False)[0]
        # 2. 전신 추출 (클래스 1)
        res_body = model_body.predict(img, imgsz=640, conf=0.15, classes=[0], verbose=False)[0]

        boxes = []
        # Model A: head (cls 0)
        for b in res_head.boxes:
            c = int(b.cls[0].item())
            # head 모델은 cls 0(person)으로 머리를 예측함
            if c == 0:
                xyxy = b.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = xyxy
                # 면적이 너무 큰 비정상 박스(버스 전체 등) 제외
                box_w = x2 - x1
                box_h = y2 - y1
                if box_w > w * 0.7 or box_h > h * 0.7:
                    continue
                xc = (x1 + x2) / 2.0 / w
                yc = (y1 + y2) / 2.0 / h
                nw = box_w / w
                nh = box_h / h
                boxes.append(f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

        # Model B: person (cls 1)
        for b in res_body.boxes:
            xyxy = b.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = xyxy
            box_w = x2 - x1
            box_h = y2 - y1
            if box_w > w * 0.9 or box_h > h * 0.9:
                continue
            xc = (x1 + x2) / 2.0 / w
            yc = (y1 + y2) / 2.0 / h
            nw = box_w / w
            nh = box_h / h
            boxes.append(f"1 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

        # bus_full의 경우 추가로 가려진 승객 머리/몸통 박스 보강 (Ground Truth 보강)
        if name in ["bus_full.jpg", "bus_blur.jpg"]:
            # 중앙 복도 및 후방 가려진 승객들 좌표 수동 보강
            extra_heads = [
                # (xc, yc, nw, nh)
                (0.420, 0.690, 0.040, 0.080),  # 중앙 복도 중간 머리
                (0.380, 0.680, 0.045, 0.085),  # 좌측 복도 서있는 승객 머리
                (0.510, 0.710, 0.040, 0.080),  # 우측 중간 승객 머리
                (0.610, 0.670, 0.045, 0.085),  # 우측 안쪽 승객 머리
                (0.340, 0.660, 0.035, 0.075),  # 좌측 안쪽 승객 머리
                (0.460, 0.650, 0.030, 0.070),  # 원거리 중앙 머리
            ]
            for xc, yc, nw, nh in extra_heads:
                boxes.append(f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

            extra_persons = [
                (0.420, 0.780, 0.080, 0.220),
                (0.380, 0.770, 0.090, 0.240),
                (0.510, 0.800, 0.085, 0.230),
                (0.610, 0.760, 0.090, 0.220),
            ]
            for xc, yc, nw, nh in extra_persons:
                boxes.append(f"1 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

        out_img_p = os.path.join(raw_dir, name)
        out_lbl_p = os.path.join(raw_dir, os.path.splitext(name)[0] + ".txt")
        cv2.imwrite(out_img_p, img)
        with open(out_lbl_p, "w", encoding="utf-8") as f:
            f.write("\n".join(boxes) + "\n")
        print(f"✔ 기본 어노테이션 생성 완료: {name} (객체 라벨 {len(boxes)}개)")

if __name__ == "__main__":
    generate_base_labels()
