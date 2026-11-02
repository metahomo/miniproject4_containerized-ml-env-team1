/* 디자인 시안 2026-11-02 — 게이지는 값을 지어내지 않는다 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BusFill, clampRatio } from "../src/components/BusFill";
import { RouteLine, routePositions } from "../src/components/RouteLine";
import type { NextVehicleItem } from "../src/api/types";

const iso = (min: number) => new Date(Date.now() + min * 60000).toISOString().slice(0, 19);

describe("BusFill", () => {
  it("정원 초과는 100 에서 멈춘다", () => { expect(clampRatio(130)).toBe(100); expect(clampRatio(-5)).toBe(0); });
  it("값이 없으면 수위를 그리지 않는다", () => {
    const { container } = render(<BusFill ratio={null} level="free" />);
    expect(container.querySelector(".bus-level")).toBeNull();
    expect(screen.getByRole("img").getAttribute("aria-label")).toBe("혼잡도 값 없음");
  });
  it("판독 불확실은 참고로 읽히고 빗금을 쓴다", () => {
    const { container } = render(<BusFill ratio={40} level="uncertain" />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain("참고");
    expect((container.querySelector(".bus-level") as SVGElement).style.fill).toContain("url");
  });
});

describe("RouteLine", () => {
  it("남은 시간이 짧을수록 정류장(100)에 가깝다", () => {
    expect(routePositions([20, 5, 0])).toEqual([0, 75, 100]);
    expect(routePositions([5])).toEqual([50]);   // 최소 축 10분
  });
  it("도착 정보 없는 차량은 놓지 않고, 실측 없는 차량은 수위를 그리지 않는다", () => {
    const vs: NextVehicleItem[] = [
      { vehicle_id: "A", expected_arrival_at: null, basis_type: "measured", vacant_ratio: 50, crowding_level: "normal", warnings: [] },
      { vehicle_id: "B", expected_arrival_at: iso(4), basis_type: "no_measurement", warnings: [] },
    ];
    const { container } = render(<RouteLine vehicles={vs} stopName="충남대학교" />);
    expect(container.querySelectorAll(".route-bus")).toHaveLength(1);
    expect(container.querySelector(".bus-level")).toBeNull();
  });
  it("놓을 차량이 없으면 그리지 않는다", () => {
    const { container } = render(<RouteLine vehicles={[]} stopName="x" />);
    expect(container.firstChild).toBeNull();
  });
});
