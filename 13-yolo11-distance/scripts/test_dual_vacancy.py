import argparse
import time
import os
import sys
import cv2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_DIR)

from src.dual_pipeline import DualModelVacancyPipeline

def parse_args():
    parser = argparse.ArgumentParser(description="YOLOv8 Head + YOLO11 Distance 이중 모델 융합 추론 (v1.3)")
    parser.add_argument("--version", action="version", version="YOLO11 Bus Distance Pipeline v1.3")
    parser.add_argument("--source", type=str, required=True, help="입력 이미지 경로")
    parser.add_argument("--out", type=str, required=True, help="출력 결과 이미지 경로")
    parser.add_argument("--capacity", type=int, default=30, help="기준 정원")
    parser.add_argument("--head-conf", type=float, default=0.12, help="Model A (두부 탐지) 신뢰도 임계값")
    parser.add_argument("--person-conf", type=float, default=0.15, help="Model B (전신 탐지) 신뢰도 임계값")
    parser.add_argument("--head-imgsz", type=int, default=1280, help="Model A 입력 해상도 (CrowdHuman 규격: 1280)")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IOU 임계값")
    return parser.parse_args()

def main():
    args = parse_args()
    if not os.path.exists(args.source):
        print(f"❌ 오류: 파일을 찾을 수 없습니다: {args.source}")
        sys.exit(1)

    img = cv2.imread(args.source)
    t0 = time.time()

    pipeline = DualModelVacancyPipeline(capacity=args.capacity)
    payload, orig_img = pipeline.infer(
        img,
        head_conf=args.head_conf,
        person_conf=args.person_conf,
        head_imgsz=args.head_imgsz,
        iou=args.iou
    )
    pipeline.visualize(orig_img, payload, args.out)

    elapsed = time.time() - t0
    s = payload["fusion_summary"]

    print("\n" + "="*55)
    print(" 🤖 [YOLOv8 Head + YOLO11 Distance 융합 분석 엔진 v1.3]")
    print("="*55)
    print(f"• 추론 총 소요 시간: {elapsed:.3f}초")
    print(f"• 설정된 파라미터: Head Conf={args.head_conf}, Person Conf={args.person_conf}, Head ImgSz={args.head_imgsz}")
    print(f"• 두부(머리) 탐지 인원 [Model A]: {s['head_count']}명")
    print(f"• 전신 탐지 인원 [Model B]: {s['person_body_count']}명")
    print(f"• 공간 점유율: {s['occupancy_ratio']}% (기준 정원 {s['capacity']}명)")
    print(f"• 평균 객체 간 거리: {s['avg_distance_px']} px")
    print(f"• 밀집 쌍 수 / 밀집률: {s['close_pairs_count']}개 / {s['crowded_ratio']*100:.1f}%")
    print(f"• 최종 여유 공간 판정: {s['vacancy_status_kr']} ({s['vacancy_status']})")
    print(f"• 렌더링 이미지: {args.out}")
    print("="*55 + "\n")

if __name__ == "__main__":
    main()
