import os
import shutil
import random
import argparse
import glob

def parse_args():
    parser = argparse.ArgumentParser(description="수집 및 라벨링된 버스 이미지/라벨을 Train/Val (8:2)로 자동 분할")
    parser.add_argument("--src-dir", type=str, required=True, help="라벨링 완료된 이미지(.jpg/.png) 및 라벨(.txt)이 함께 모여있는 원본 디렉터리")
    parser.add_argument("--dest-dir", type=str, default="datasets/bus_crowd", help="데이터셋 루트 경로 (기본: datasets/bus_crowd)")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation 데이터 비율 (기본: 0.2)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    return parser.parse_args()

def main():
    args = parse_args()
    random.seed(args.seed)

    if not os.path.exists(args.src_dir):
        print(f"❌ 원본 디렉터리가 없습니다: {args.src_dir}")
        return

    exts = ("*.jpg", "*.jpeg", "*.png")
    image_paths = []
    for ext in exts:
        image_paths.extend(glob.glob(os.path.join(args.src_dir, ext)))

    if not image_paths:
        print(f"❌ '{args.src_dir}' 디렉터리 내에 이미지가 없습니다.")
        return

    # 라벨 매칭 검증
    valid_pairs = []
    for img_p in image_paths:
        base_name = os.path.splitext(img_p)[0]
        lbl_p = base_name + ".txt"
        if os.path.exists(lbl_p):
            valid_pairs.append((img_p, lbl_p))
        else:
            print(f"⚠️ 라벨 파일 미발견: {lbl_p} (건너뜀)")

    print(f" 총 {len(valid_pairs)}쌍의 유효한 (이미지, 라벨) 데이터가 확인되었습니다.")
    if not valid_pairs:
        return

    random.shuffle(valid_pairs)
    val_count = int(len(valid_pairs) * args.val_ratio)
    train_pairs = valid_pairs[val_count:]
    val_pairs = valid_pairs[:val_count]

    # 목적지 폴더 생성
    for subset in ["train", "val"]:
        os.makedirs(os.path.join(args.dest_dir, "images", subset), exist_ok=True)
        os.makedirs(os.path.join(args.dest_dir, "labels", subset), exist_ok=True)

    def copy_pairs(pairs, subset):
        for img_p, lbl_p in pairs:
            shutil.copy2(img_p, os.path.join(args.dest_dir, "images", subset, os.path.basename(img_p)))
            shutil.copy2(lbl_p, os.path.join(args.dest_dir, "labels", subset, os.path.basename(lbl_p)))

    copy_pairs(train_pairs, "train")
    copy_pairs(val_pairs, "val")

    print(f"✔ 분할 완료! Train: {len(train_pairs)}장, Val: {len(val_pairs)}장")
    print(f"✔ 결과 저장 위치: {args.dest_dir}")

if __name__ == "__main__":
    main()
