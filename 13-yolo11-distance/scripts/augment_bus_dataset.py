import os
import glob
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

def augment_image_and_labels(img, labels):
    """단일 이미지와 라벨에 대해 다양한 버스 환경 증강 세트 생성"""
    h, w = img.shape[:2]
    augmented = []

    # 1. 원본
    augmented.append(("orig", img.copy(), labels))

    # 2. 좌우 반전 (Horizontal Flip)
    img_flip = cv2.flip(img, 1)
    labels_flip = []
    for cls_id, xc, yc, nw, nh in labels:
        labels_flip.append((cls_id, 1.0 - xc, yc, nw, nh))
    augmented.append(("flip", img_flip, labels_flip))

    # 3. 야간 / 터널 환경 (저조도)
    img_dark = cv2.convertScaleAbs(img, alpha=0.6, beta=-30)
    augmented.append(("dark", img_dark, labels))

    # 4. 강한 역광 / 직사광선 (고조도)
    img_bright = cv2.convertScaleAbs(img, alpha=1.2, beta=35)
    augmented.append(("bright", img_bright, labels))

    # 5. 주행 진동 / 모션 블러
    ksize = 5
    kernel = np.zeros((ksize, ksize))
    kernel[int((ksize-1)/2), :] = np.ones(ksize)
    kernel /= ksize
    img_motion = cv2.filter2D(img, -1, kernel)
    augmented.append(("motion_blur", img_motion, labels))

    # 6. 센서 노이즈 (저조도 ISO 노이즈)
    noise = np.random.normal(0, 12, img.shape).astype(np.uint8)
    img_noise = cv2.add(img, noise)
    augmented.append(("noise", img_noise, labels))

    # 7. 색조 변화 (황색 가로등 / 실내 LED 조명)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 0] = (hsv[:, :, 0] + 15) % 180
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.15, 0, 255)
    img_color = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    augmented.append(("warm_led", img_color, labels))

    # 8. 반전 + 야간 (복합 증강)
    img_flip_dark = cv2.convertScaleAbs(img_flip, alpha=0.65, beta=-25)
    augmented.append(("flip_dark", img_flip_dark, labels_flip))

    # 9. 반전 + 고조도 (복합 증강)
    img_flip_bright = cv2.convertScaleAbs(img_flip, alpha=1.15, beta=30)
    augmented.append(("flip_bright", img_flip_bright, labels_flip))

    # 10. 반전 + 블러
    img_flip_blur = cv2.GaussianBlur(img_flip, (5, 5), 0)
    augmented.append(("flip_blur", img_flip_blur, labels_flip))

    return augmented

def main():
    src_dir = os.path.join(PROJECT_DIR, "data", "raw_bus_annotated")
    out_dir = os.path.join(PROJECT_DIR, "data", "bus_augmented_pool")
    os.makedirs(out_dir, exist_ok=True)

    img_files = glob.glob(os.path.join(src_dir, "*.jpg"))
    total_generated = 0

    for img_path in img_files:
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        lbl_path = os.path.join(src_dir, f"{base_name}.txt")
        if not os.path.exists(lbl_path):
            continue

        img = cv2.imread(img_path)
        labels = []
        with open(lbl_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    labels.append((int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])))

        aug_list = augment_image_and_labels(img, labels)
        for tag, aug_img, aug_lbl in aug_list:
            save_img_name = f"{base_name}_{tag}.jpg"
            save_lbl_name = f"{base_name}_{tag}.txt"
            
            cv2.imwrite(os.path.join(out_dir, save_img_name), aug_img)
            with open(os.path.join(out_dir, save_lbl_name), "w", encoding="utf-8") as f:
                for cls_id, xc, yc, nw, nh in aug_lbl:
                    f.write(f"{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")
            total_generated += 1

    print(f"🎉 총 {total_generated}장의 차내 특화 증강 데이터셋이 생성되었습니다: {out_dir}")

if __name__ == "__main__":
    main()
