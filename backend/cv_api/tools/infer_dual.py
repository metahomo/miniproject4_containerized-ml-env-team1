"""v1.3: YOLOv8 Head + YOLO11 이중 융합 모델 단독 CLI 추론 도구."""
import argparse
import os
import sys
import time
import cv2

from ..predict import DualModelDetector
from ..settings import get_settings


def parse_args():
    parser = argparse.ArgumentParser(description="sumtong v1.3 YOLOv8 Head + YOLO11 융합 모델 CLI 추론")
    parser.add_argument("--version", action="version", version="sumtong Dual Inference Engine v1.3")
    parser.add_argument("--source", type=str, required=True, help="입력 이미지 경로 (예: samples/bus_full.jpg)")
    parser.add_argument("--out", type=str, default="", help="출력 시각화 이미지 경로 (선택)")
    parser.add_argument("--capacity", type=int, default=30, help="기준 차량 정원 (기본값: 30)")
    parser.add_argument("--distance-threshold", type=float, default=150.0, help="근접 위험 거리 임계값(px)")
    return parser.parse_args()


def main():
    args = parse_args()
    if not os.path.exists(args.source):
        print(f"오류: 입력 파일을 찾을 수 없습니다: {args.source}")
        sys.exit(1)

    img = cv2.imread(args.source)
    if img is None:
        print(f"오류: 이미지 디코드 실패: {args.source}")
        sys.exit(1)

    s = get_settings()
    if args.distance_threshold:
        s.DISTANCE_THRESHOLD = args.distance_threshold

    print("이중 모델(YOLOv8 Head + YOLO11)을 로드하는 중...")
    t0 = time.perf_counter()
    detector = DualModelDetector(s)
    detector.load()
    load_ms = int((time.perf_counter() - t0) * 1000)

    print(f"모델 로드 완료 ({load_ms}ms). 추론을 시작합니다...")
    t1 = time.perf_counter()
    payload = detector.infer_dual(img, capacity=args.capacity)
    infer_ms = int((time.perf_counter() - t1) * 1000)

    summary = payload["fusion_summary"]
    print("\n" + "=" * 60)
    print(" [sumtong v1.3: YOLOv8 Head + YOLO11 이중 융합 분석 결과]")
    print("=" * 60)
    print(f"* 추론 소요 시간: {infer_ms}ms")
    print(f"* 두부 탐지 승객 수 [Model A]: {summary['head_count']}명")
    print(f"* 전신 탐지 승객 수 [Model B]: {summary['person_body_count']}명")
    print(f"* 객실 점유율: {summary['occupancy_ratio']}% (기준 정원: {summary['capacity']}명)")
    print(f"* 승객 간 평균 거리: {summary['avg_distance_px']} px")
    print(f"* 밀집 근접 쌍 / 밀집 비율: {summary['close_pairs_count']}개 / {summary['crowded_ratio']*100:.1f}%")
    print(f"* 객실 상태 판정: {summary['vacancy_status_kr']} ({summary['vacancy_status']})")

    if args.out:
        annotated = detector.annotate_image(img, payload)
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        cv2.imwrite(args.out, annotated)
        print(f"* 시각화 이미지 저장 완료: {args.out}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
