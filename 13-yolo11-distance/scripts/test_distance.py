import argparse
import time
import json
import os
import sys
import cv2
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_DIR)

from src.pipeline import DistancePipeline

def parse_args():
    parser = argparse.ArgumentParser(description="YOLO11 Distance Pipeline Verification")
    parser.add_argument("--source", type=str, default=None, help="테스트 이미지 경로")
    parser.add_argument("--smoke", action="store_true", help="3초 이내 빠른 기능 검증 모드")
    return parser.parse_args()

def main():
    args = parse_args()
    start_time = time.time()

    pipeline = DistancePipeline()

    if args.source and os.path.exists(args.source):
        test_img = cv2.imread(args.source)
    else:
        # 스모크 테스트용 인메모리 합성 이미지 (640x640) 생성
        test_img = np.full((640, 640, 3), 220, dtype=np.uint8)
        cv2.rectangle(test_img, (120, 150), (220, 450), (40, 40, 40), -1)
        cv2.rectangle(test_img, (260, 150), (360, 450), (40, 40, 40), -1)

    payload, orig_img = pipeline.infer(test_img)

    save_path = os.path.join(PROJECT_DIR, "results", "smoke_result.jpg")
    pipeline.visualize(orig_img, payload, save_path)

    elapsed = time.time() - start_time

    print(f"\n[INFO] 소요 시간: {elapsed:.3f}초")
    print(f"[INFO] 결과 저장 경로: {save_path}")
    print("[INFO] 반환 JSON 규격:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.smoke:
        assert elapsed < 3.0, f"❌ DoD 실패: 실행 시간 초과 ({elapsed:.2f}s >= 3.0s)"
        assert os.path.exists(save_path), "❌ DoD 실패: 결과 이미지 미생성"
        print("\n✅ [DoD 통과] --smoke 테스트 성공 (3초 이내 완료 및 시각화 저장 확인)")

if __name__ == "__main__":
    main()
