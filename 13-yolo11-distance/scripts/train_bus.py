import os
import sys
import argparse
import shutil
import glob
import torch
from ultralytics import YOLO

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SUMTONG_ROOT = os.path.abspath(os.path.join(PROJECT_DIR, ".."))

def parse_args():
    parser = argparse.ArgumentParser(description="버스 환경 특화 YOLOv8 Head & YOLO11 추가 학습(Fine-tuning)")
    parser.add_argument("--data", type=str, default=os.path.join(PROJECT_DIR, "datasets", "bus_crowd", "data.yaml"), help="data.yaml 경로")
    parser.add_argument("--epochs", type=int, default=50, help="훈련 에포크 수 (기본 50)")
    parser.add_argument("--batch-head", type=int, default=4, help="Head 모델 배치 크기 (기본 4)")
    parser.add_argument("--batch-body", type=int, default=8, help="Body 모델 배치 크기 (기본 8)")
    parser.add_argument("--device", type=str, default=None, help="학습 디바이스 ('0', 'cpu', 기본: 자동 감지)")
    parser.add_argument("--workers", type=int, default=2, help="데이터 로더 워커 수")
    parser.add_argument("--skip-head", action="store_true", help="Head 모델 학습 건너뛰기")
    parser.add_argument("--skip-body", action="store_true", help="Body 모델 학습 건너뛰기")
    parser.add_argument("--deploy", action="store_true", help="학습 완료 후 backend/models로 best.pt 자동 배포")
    return parser.parse_args()

def validate_dataset(data_yaml_path):
    train_dir = os.path.join(os.path.dirname(data_yaml_path), "images", "train")
    val_dir = os.path.join(os.path.dirname(data_yaml_path), "images", "val")
    
    train_images = glob.glob(os.path.join(train_dir, "*.*"))
    val_images = glob.glob(os.path.join(val_dir, "*.*"))

    print(f"📊 [데이터셋 사전 점검] train 이미지: {len(train_images)}장, val 이미지: {len(val_images)}장")
    if len(train_images) == 0:
        print("⚠️ [경고] datasets/bus_crowd/images/train 디렉터리에 학습용 이미지가 없습니다!")
        print("💡 라벨링된 이미지와 .txt 파일을 train 및 val 폴더에 배치한 후 학습을 시작해 주세요.")
        return False
    return True

def main():
    args = parse_args()
    
    # 0. 디바이스 자동 감지
    if args.device is None:
        device = 0 if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    print("=" * 60)
    print(" 🚀 [버스 환경 맞춤형 이중 모델 추가 학습(Fine-tuning) 파이프라인]")
    print("=" * 60)
    print(f"• 설정 디바이스: {device} (CUDA 지원 여부: {torch.cuda.is_available()})")
    print(f"• 데이터 설정 파일: {args.data}")
    print(f"• 설정 에포크: {args.epochs}")
    print("=" * 60)

    # 데이터셋 존재 여부 확인
    if not os.path.exists(args.data):
        print(f"❌ 오류: data.yaml 파일을 찾을 수 없습니다: {args.data}")
        sys.exit(1)

    if not validate_dataset(args.data):
        print("\n⛔ 이미지 데이터가 아직 준비되지 않아 학습을 시작하지 않고 사전 점검을 마칩니다.")
        print("   준비가 완료되면 다시 이 스크립트를 실행해 주세요.")
        sys.exit(0)

    head_base = os.path.join(SUMTONG_ROOT, "backend", "models", "head_crowdhuman_n1280.pt")
    yolo11_base = os.path.join(SUMTONG_ROOT, "backend", "models", "yolo11n.pt")

    # 1. Model A: YOLOv8 Head 모델 추가 학습 (CrowdHuman 특화 해상도 1280 유지)
    if not args.skip_head:
        print("\n🔹 [Step 1/2] YOLOv8 Head 모델 추가 학습 시작...")
        if os.path.exists(head_base):
            model_head = YOLO(head_base)
            model_head.train(
                data=args.data,
                epochs=args.epochs,
                imgsz=1280,
                batch=args.batch_head,
                device=device,
                project=os.path.join(PROJECT_DIR, "runs", "train"),
                name="bus_head_v8",
                workers=args.workers,
                exist_ok=True
            )
            print("✅ Model A (Head) 추가 학습 완료!")
        else:
            print(f"❌ 기본 모델 미발견: {head_base}")
    else:
        print("⏩ Model A 학습을 건너뜁니다.")

    # 2. Model B: YOLO11 전신/거리 모델 추가 학습 (해상도 640)
    if not args.skip_body:
        print("\n🔹 [Step 2/2] YOLO11 전신/거리 모델 추가 학습 시작...")
        if os.path.exists(yolo11_base):
            model_yolo11 = YOLO(yolo11_base)
            model_yolo11.train(
                data=args.data,
                epochs=args.epochs,
                imgsz=640,
                batch=args.batch_body,
                device=device,
                project=os.path.join(PROJECT_DIR, "runs", "train"),
                name="bus_person_yolo11",
                workers=args.workers,
                exist_ok=True
            )
            print("✅ Model B (Body) 추가 학습 완료!")
        else:
            print(f"❌ 기본 모델 미발견: {yolo11_base}")
    else:
        print("⏩ Model B 학습을 건너뜁니다.")

    # 3. 모델 가중치 배포 (선택)
    if args.deploy:
        print("\n📦 [Step 3] 학습된 최적 가중치(best.pt) 공식 백엔드 모델로 복사 중...")
        best_head = os.path.join(PROJECT_DIR, "runs", "train", "bus_head_v8", "weights", "best.pt")
        best_body = os.path.join(PROJECT_DIR, "runs", "train", "bus_person_yolo11", "weights", "best.pt")

        if os.path.exists(best_head):
            shutil.copy2(best_head, head_base)
            print(f"✔ Model A 가중치 업데이트 완료: {head_base}")
        if os.path.exists(best_body):
            shutil.copy2(best_body, yolo11_base)
            print(f"✔ Model B 가중치 업데이트 완료: {yolo11_base}")

    print("\n🎉 모든 파이프라인 프로세스가 정상적으로 종료되었습니다.")

if __name__ == "__main__":
    main()
