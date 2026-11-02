/* 디자인 확인용 예시 응답 — 개발 서버의 /?preview=1 에서만 쓴다. 서버·DB 를 거치지 않고, 화면에 «예시 데이터»로 표시한다. */
import type { NextVehicleItem, NextVehicleResponse } from "../api/types";

const iso = (min: number) => new Date(Date.now() + min * 60000).toISOString().slice(0, 19);
const bus = (id: string, min: number, level: NextVehicleItem["crowding_level"], vacant: number, persons: number): NextVehicleItem => ({
  vehicle_id: id, expected_arrival_at: iso(min), basis_type: "measured", vacant_ratio: vacant, persons_sum: persons, capacity: 80,
  crowding_level: level, measured_at: iso(-2), coverage_num: 2, coverage_den: 2, warnings: [],
});

export const previewResponse = (): NextVehicleResponse => ({
  route_id: "preview", stop_id: "preview", place_kind: "bus_stop", applied_validity_minutes: 8, validity_source: "default", demo_mode: false, fetched_at: iso(0), source_status: "ok",
  notice: "이 수치는 영상 프레임을 바탕으로 한 통계적 추정치이며 실제 탑승 가능 여부를 보장하지 않습니다.",
  vehicles: [
    bus("예시1", 2, "crowded", 12, 70), bus("예시2", 7, "free", 68, 26), bus("예시3", 12, "uncertain", 45, 44),
    { vehicle_id: "예시4", expected_arrival_at: iso(18), basis_type: "no_measurement", warnings: [] },
  ],
});
