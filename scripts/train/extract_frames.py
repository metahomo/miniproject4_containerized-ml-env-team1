"""1단계 — 차내 CCTV 영상에서 학습용 프레임을 뽑는다.

  python scripts/train/extract_frames.py 영상.mp4 --source daejeon-bus --camera CAM-B101 --date 20261001 \
      --every 3 --out datasets/transit_head/images/pool

- 연속 프레임은 거의 같으므로 --every 초(기본 3초)마다 1장. 흐린 장면(라플라시안 분산 < --blur-min)은 건너뛴다.
- 파일 이름 = <출처>__<카메라>__<날짜>__<초>.jpg (split.py 가 앞 세 칸으로 그룹을 나눈다).
- 학습 데이터는 원본 영상 프레임이다. 서비스의 FR-11(원본 미저장)과 별개로 기관 승인·가명처리 협의를 거친 영상만 쓴다.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--source", required=True, help="출처 (예: daejeon-bus, daejeon-metro)")
    ap.add_argument("--camera", required=True, help="카메라 ID")
    ap.add_argument("--date", required=True, help="촬영일 YYYYMMDD")
    ap.add_argument("--every", type=float, default=3.0, help="몇 초마다 1장 (기본 3)")
    ap.add_argument("--blur-min", type=float, default=60.0, help="이보다 흐린 장면은 건너뜀 (라플라시안 분산)")
    ap.add_argument("--max-side", type=int, default=1920, help="긴 변 상한 px")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    total = 0
    for vi, video in enumerate(a.videos):
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f"[건너뜀] 열 수 없음: {video}")
            continue
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps * a.every))
        idx = kept = blurred = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if idx % step == 0:
                ok, img = cap.retrieve()
                if ok:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    if cv2.Laplacian(gray, cv2.CV_64F).var() < a.blur_min:
                        blurred += 1
                    else:
                        h, w = img.shape[:2]
                        if max(h, w) > a.max_side:
                            r = a.max_side / max(h, w)
                            img = cv2.resize(img, (round(w * r), round(h * r)), interpolation=cv2.INTER_AREA)
                        sec = idx / fps
                        name = f"{a.source}__{a.camera}__{a.date}__v{vi:02d}t{int(sec * 10):07d}.jpg"   # t = 0.1초 단위
                        cv2.imwrite(str(a.out / name), img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                        kept += 1
            idx += 1
        cap.release()
        total += kept
        print(f"{video.name}: {kept}장 저장, 흐림 {blurred}장 건너뜀 ({a.every:g}초 간격)")
    print(f"합계 {total}장 → {a.out}")


if __name__ == "__main__":
    main()
