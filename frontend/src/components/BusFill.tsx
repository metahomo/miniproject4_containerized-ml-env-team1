/* 버스 수위 게이지 (디자인 시안 2026-11-02) — 혼잡도를 버스 실루엣에 아래에서 위로 차오르는 수위로 그린다.
   좌석·칸으로 나누지 않는다: 시스템은 머릿수만 추정하므로 "어느 자리가 비었나"로 읽히면 안 된다.
   등급 표현은 style-guide §6 을 따른다: 판독 불확실 = 회색 빗금(확정값과 구분), 값 없음 = 점선 빈 버스.
   색만으로 전달하지 않는다 — 등급 글자는 곁의 StatusBadge 가 맡는다. */
import { useId } from "react";

const TANK = { x: 4, y: 6, w: 112, h: 38 };

/** 0~100 으로 자른 비율. 값이 없으면 null (정원 초과는 100 에서 멈춘다, R22) */
export const clampRatio = (ratio?: number | null) => (ratio == null || Number.isNaN(ratio) ? null : Math.min(100, Math.max(0, ratio)));

export function BusFill({ ratio, level, width = 120 }: { ratio?: number | null; level?: string | null; width?: number }) {
  const id = useId().replace(/:/g, "");
  const r = clampRatio(ratio);
  const hatch = level === "uncertain";
  const label = r === null ? "혼잡도 값 없음" : `${hatch ? "참고 " : ""}혼잡 약 ${r.toFixed(0)}% 게이지`;
  return (
    <svg className={"bus-fill" + (r === null ? " empty" : "") + (level ? ` level-${level}` : "")} viewBox="0 0 120 56" width={width} role="img" aria-label={label}>
      <defs>
        <clipPath id={`${id}c`}><rect x={TANK.x} y={TANK.y} width={TANK.w} height={TANK.h} rx="7" /></clipPath>
        <pattern id={`${id}h`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="2.5" height="6" style={{ fill: "var(--status-uncertain)" }} />
        </pattern>
      </defs>
      <rect className="bus-tank" x={TANK.x} y={TANK.y} width={TANK.w} height={TANK.h} rx="7" />
      {r !== null && (
        <g clipPath={`url(#${id}c)`}>
          <rect className="bus-level" x="0" y={TANK.y} width="120" height={TANK.h}
            style={{ transform: `translateY(${TANK.h * (1 - r / 100)}px)`, ...(hatch ? { fill: `url(#${id}h)` } : {}) }} />
        </g>
      )}
      <rect className="bus-body" x={TANK.x} y={TANK.y} width={TANK.w} height={TANK.h} rx="7" />
      <path className="bus-glass" d="M98 6v16h18" />
      <circle className="bus-wheel" cx="30" cy="46" r="7" />
      <circle className="bus-wheel" cx="90" cy="46" r="7" />
    </svg>
  );
}
