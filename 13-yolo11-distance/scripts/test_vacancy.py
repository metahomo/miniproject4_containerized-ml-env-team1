import argparse
import json
import os
import sys
import cv2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../.."))
sys.path.append(os.path.abspath(os.path.join(CURRENT_DIR, "..")))

from src.vacancy_pipeline import VacancyDistancePipeline

def parse_args():
    parser = argparse.ArgumentParser(description="인원 수 및 거리 기반 공간 여유도 추론")
    parser.add_argument("--source", type=str, required=True, help="분석할 이미지 경로")
    parser.add_argument("--out", type=str, default="results/vacancy_result.jpg", help="결과 이미지 저장 경로")
    parser.add_argument("--threshold", type=float, default=150.0, help="밀집 판별 거리 기준(px)")
    parser.add_argument("--capacity", type=int, default=30, help="공간 기준 정원")
    return parser.parse_args()

def main():
    args = parse_args()
    if not os.path.exists(args.source):
        print(f"❌ 오류: 입력 파일을 찾을 수 없습니다: {args.source}")
        sys.exit(1)

    img = cv2.imread(args.source)
    pipeline = VacancyDistancePipeline(distance_threshold=args.threshold, capacity=args.capacity)
    payload, orig_img = pipeline.infer(img)

    out_path = os.path.join(PROJECT_ROOT, "13-yolo11-distance", args.out)
    pipeline.visualize(orig_img, payload, out_path)

    print("\n" + "="*50)
    print(" 📊 [공간 여유도 및 밀집도 분석 결과]")
    print("="*50)
    print(f"• 탑승/재실 인원: {payload['space_analysis']['head_count']}명 (정원 {payload['space_analysis']['capacity']}명)")
    print(f"• 공간 점유율: {payload['space_analysis']['occupancy_ratio']}%")
    print(f"• 평균 객체 간 거리: {payload['space_analysis']['avg_distance_px']} px")
    print(f"• 밀집 쌍 수: {payload['space_analysis']['close_pairs_count']}개 (밀집 비율: {payload['space_analysis']['crowded_ratio']*100:.1f}%)")
    print(f"• 판정 결과: {payload['space_analysis']['vacancy_status_kr']} ({payload['space_analysis']['vacancy_status']})")
    print(f"• 결과 이미지 저장: {out_path}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()