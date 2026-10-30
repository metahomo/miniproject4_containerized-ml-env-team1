/* 재생하며 실시간 진단 — 칸 계산·칸 사이 값 유지·안정 인원(최근 N칸 중앙값 + 연속 확인, R22 인원 ÷ 정원) */
import { describe, expect, it } from "vitest";
import { currentOf, heldSlot, levelOf, slotCount, slotOf, stableSeries, type Slot } from "../src/components/LiveVideoDiagnosis";
import type { Assessment } from "../src/api/types";

/* v = 이번 장면 인원. 정원 80 (서버 테스트 픽스처와 같게) */
const acc = (t: number, v: number, lvl = "normal", capacity: number | null = 80): Slot => ({ t, status: "accepted", assessment: { person_count: v, capacity, crowding_level: lvl } as Assessment });
const seq = (vals: number[], lvl = "normal") => Object.fromEntries(vals.map((v, i) => [i, acc(i * 2, v, lvl)])) as Record<number, Slot>;
const thr = { free_min: 50, crowded_max: 20 };
const rej = (t: number): Slot => ({ t, status: "rejected", reject: { gate: "G2", reason_code: "BLUR", reason: "흐림", resolver_role: "self" } });

describe("칸 계산", () => {
  it("재생 위치 → 칸 번호, 영상 길이 → 칸 수", () => {
    expect(slotOf(0, 2)).toBe(0);
    expect(slotOf(1.99, 2)).toBe(0);
    expect(slotOf(2, 2)).toBe(1);
    expect(slotOf(5.5, 1)).toBe(5);
    expect(slotCount(10, 2)).toBe(5);
    expect(slotCount(10.5, 2)).toBe(6);
    expect(slotCount(0, 2)).toBe(1);
  });
});

describe("칸 사이 값 유지", () => {
  it("현재 칸이 비어 있으면 직전에 받은 칸, 앞선 칸이 없으면 null", () => {
    const s = { 0: acc(0.1, 40), 3: acc(6.2, 60) };
    expect(heldSlot(s, 2)).toBe(0);
    expect(heldSlot(s, 3)).toBe(3);
    expect(heldSlot(s, 9)).toBe(3);
    expect(heldSlot({ 4: acc(8, 1) }, 2)).toBeNull();
  });
});

describe("안정 인원 (R22)", () => {
  it("사람이 그대로인데 한두 칸 튀는 인원(애매한 검출)은 표시 인원을 바꾸지 않는다", () => {
    const st = stableSeries(seq([30, 30, 31, 30, 30, 29, 30, 30]), 5, 2, thr);
    expect(Object.values(st).map((x) => x.persons)).toEqual([30, 30, 30, 30, 30, 30, 30, 30]);
    expect(st[7].raw).toBe(30);
    expect(st[2].raw).toBe(31);
  });
  it("실제로 바뀐 인원은 중앙값이 같은 방향으로 2칸 연속 달라진 뒤 따라간다", () => {
    const st = stableSeries(seq([20, 20, 20, 60, 60, 60, 60, 60]), 5, 2, thr);
    expect(Object.values(st).map((x) => x.persons)).toEqual([20, 20, 20, 20, 20, 20, 60, 60]);
    expect(st[0].occupied).toBe(25);           // 20 ÷ 80
    expect(st[0].level).toBe("free");          // 여유 75% ≥ 50
    expect(st[7].occupied).toBe(75);
    expect(st[7].level).toBe("normal");        // 여유 25% — 기준 50/20 사이
  });
  it("정원 초과는 100% 에서 멈추고 표시, 정원이 없으면 혼잡도 산출 불가", () => {
    const st = stableSeries(seq([90, 90]), 5, 2, thr);
    expect(st[1].occupied).toBe(100);
    expect(st[1].vacant).toBe(0);
    expect(st[1].over).toBe(true);
    expect(st[1].level).toBe("crowded");
    const none = stableSeries({ 0: acc(0, 12, "uncertain", null) }, 5, 2, thr)[0];
    expect([none.persons, none.capacity, none.occupied, none.level, none.reference]).toEqual([12, null, null, null, false]);
  });
  it("창의 절반 넘게 판독 불확실이면 참고, 기준값이 없으면 창 안 최근 확정 등급", () => {
    const s = { ...seq([60, 60, 60], "uncertain"), 3: acc(6, 60, "free") };
    const st = stableSeries(s, 5, 2, null);
    expect(st[2].reference).toBe(true);
    expect(st[2].level).toBeNull();
    expect(st[3].reference).toBe(true);        // 4칸 중 확정 1칸
    expect(st[3].level).toBe("free");
    expect(stableSeries(seq([60, 60]), 5, 2, null)[1].reference).toBe(false);
  });
  it("반려 칸은 건너뛰고, 등급 규칙은 서버 map_level 과 같다", () => {
    expect(Object.keys(stableSeries({ 0: acc(0, 6), 1: rej(2), 2: acc(4, 6) }))).toEqual(["0", "2"]);
    expect([levelOf(50, thr), levelOf(49, thr), levelOf(20, thr)]).toEqual(["free", "normal", "crowded"]);
  });
});

describe("현재 인원 (T089)", () => {
  const A = (o: Partial<Assessment>) => ({ person_count: 31, capacity: 80, occupied_area_ratio: 38.75, vacant_capacity_ratio: 61.25, crowding_level: "free", over_capacity: false, ...o }) as Assessment;
  it("방금 분석한 장면의 서버 값을 그대로 쓴다 — 안정 인원과 달리 바로 바뀐다", () => {
    expect(currentOf(A({}), thr)).toEqual({ persons: 31, capacity: 80, occupied: 38.75, vacant: 61.25, over: false, level: "free", reference: false });
    const st = stableSeries(seq([30, 30, 30, 31]), 5, 2, thr);
    expect(st[3].persons).toBe(30);                                  // 안정 인원은 아직 30
    expect(currentOf(A({ person_count: 31 }), thr).persons).toBe(31); // 현재 인원은 31
  });
  it("판독 불확실 장면은 참고 — 기준값이 있으면 값의 등급, 없으면 등급 없음. 정원 없으면 혼잡도 없음", () => {
    expect(currentOf(A({ crowding_level: "uncertain", vacant_capacity_ratio: 15, occupied_area_ratio: 85 }), thr)).toMatchObject({ level: "crowded", reference: true });
    expect(currentOf(A({ crowding_level: "uncertain" }), null)).toMatchObject({ level: null, reference: true });
    expect(currentOf(A({ capacity: null, crowding_level: "uncertain" }), thr)).toMatchObject({ capacity: null, occupied: null, level: null, reference: false });
    expect(currentOf(A({ person_count: 90, occupied_area_ratio: 100, vacant_capacity_ratio: 0, over_capacity: true, crowding_level: "crowded" }), thr)).toMatchObject({ over: true, occupied: 100 });
  });
});
