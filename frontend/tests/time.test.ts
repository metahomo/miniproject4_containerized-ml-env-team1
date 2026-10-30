/* 시각 표시 — 서버는 UTC, 화면 표시·입력은 한국 시각(KST, UTC+9) */
import { describe, expect, it } from "vitest";
import { fmtTime, hhmm, kst, kstDate, kstInputToUtc } from "../src/api/client";

describe("한국 시각", () => {
  it("서버 UTC 를 한국 시각으로 보인다 (날짜 넘김 포함)", () => {
    expect(kst("2026-09-29T04:14:00")).toBe("2026-09-29 13:14:00");
    expect(hhmm("2026-09-29T04:14:00")).toBe("13:14");
    expect(hhmm("2026-09-29T04:14:05", true)).toBe("13:14:05");
    expect(kstDate("2026-09-29T16:30:00")).toBe("2026-09-30");      // UTC 16:30 = 한국 다음 날 01:30
    expect(fmtTime(null)).toBe("—");
  });
  it("한국 시각 입력을 UTC 로 보낸다", () => {
    expect(kstInputToUtc("2026-09-29T13:14:00")).toBe("2026-09-29T04:14:00");
    expect(kstInputToUtc("2026-09-30 01:30")).toBe("2026-09-29T16:30:00");
    expect(kstInputToUtc("")).toBe("");
  });
});
