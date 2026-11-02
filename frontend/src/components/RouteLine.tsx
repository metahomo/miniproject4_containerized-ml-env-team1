/* 도착 노선도 (디자인 시안 2026-11-02) — 다가오는 버스를 «내 정류장까지 남은 시간» 순서로 한 줄에 놓는다.
   거리·실제 위치가 아니라 도착 예정 시간 축이다. 도착 정보가 없는 차량은 놓지 않는다(자리를 지어내지 않는다).
   같은 내용은 아래 버스 목록이 글로 준다 — 여기는 한눈에 보기용이라 읽기 도구에는 요약 한 줄만 준다. */
import { minutesFromNow } from "../api/client";
import type { NextVehicleItem } from "../api/types";
import { BusFill } from "./BusFill";

const MIN_SCALE_MIN = 10;   // 버스가 모두 가까워도 축이 한 점으로 뭉치지 않게

/** 도착까지 남은 분 → 축 위치(%). 정류장 = 100 */
export function routePositions(minutes: number[]): number[] {
  const scale = Math.max(MIN_SCALE_MIN, ...minutes);
  return minutes.map((m) => 100 - (Math.max(0, m) / scale) * 100);
}

export function RouteLine({ vehicles, stopName }: { vehicles: NextVehicleItem[]; stopName: string }) {
  const placed = vehicles
    .map((v) => ({ v, m: minutesFromNow(v.expected_arrival_at) }))
    .filter((x): x is { v: NextVehicleItem; m: number } => x.m !== null)
    .sort((a, b) => b.m - a.m);
  if (!placed.length) return null;
  const pos = routePositions(placed.map((x) => x.m));
  return (
    <div className="route-line" role="img" aria-label={`${stopName} 도착 예정 버스 ${placed.length}대의 도착 순서`}>
      <div className="route-track" aria-hidden>
        {placed.map(({ v, m }, i) => {
          const measured = v.basis_type === "measured";
          return (
            <div key={v.vehicle_id ?? i} className={"route-bus" + (i % 2 ? " lane-b" : "")} style={{ left: `${pos[i]}%` }}>
              <BusFill ratio={measured && v.vacant_ratio != null ? 100 - v.vacant_ratio : null} level={measured ? v.crowding_level : null} width={58} />
              <span className="t-caption">{m <= 0 ? "곧 도착" : `약 ${m}분`}</span>
            </div>
          );
        })}
        <span className="route-stop" />
      </div>
      <div className="route-axis t-caption muted"><span>먼 버스</span><b>{stopName}</b></div>
    </div>
  );
}
