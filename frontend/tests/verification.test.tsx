/* S4 정확도 검증 — 사람이 센 인원 입력 → 잔여 %·등급 미리보기·인원 차이, 판정 요청 본문은 manual_persons (2026-09-30) */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Verification from "../src/pages/admin/Verification";

const res = (body: unknown) => ({ ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }) as unknown as Response;
const A = { assessment_id: 1, camera_id: "CAM-DEMO-01", occupied_area_ratio: 82.5, vacant_capacity_ratio: 17.5, crowding_level: "crowded", is_reference_only: false,
  person_count: 66, capacity: 80, remaining_not_computable: false, mean_confidence: 0.8, warnings: [], notice: "", processed_at: "2026-09-30T01:00:00", response_ms: 100,
  versions: { roi_id: 1, spec_id: 1, threshold_policy_id: 1, model_commit: "abc" } };
const BATCH = { batch_id: 9, camera_id: "CAM-DEMO-01", items: [{ seq: 1, status: "accepted", assessment: A }],
  consistency: { roi_id: 1, spec_id: 1, threshold_policy_id: 1, frames_discarded: 1, audit_records: 1 } };

afterEach(() => vi.unstubAllGlobals());

describe("정확도 검증 — 사람이 센 인원", () => {
  it("인원을 넣으면 잔여 %·등급·인원 차이를 보이고, 판정은 manual_persons 로 보낸다", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) =>
      url.endsWith("/v1/reference/threshold") ? res({ policy_id: 1, free_min_ratio: 50, crowded_max_ratio: 20 })
        : url.endsWith("/v1/diagnose/batch") ? res(BATCH)
        : res({ run_id: 3, batch_id: 9, ratio_match_rate: 100, level_match_rate: 100, verdict: "pass", versions: {}, items: [{ seq: 1, persons_diff: 2 }], _body: init?.body }));
    vi.stubGlobal("fetch", f);
    const { container } = render(<MemoryRouter><Verification /></MemoryRouter>);
    const input = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.jpg", { type: "image/jpeg" })] } });
    fireEvent.click(screen.getByText("검증 실행 (1장)"));
    fireEvent.change(await screen.findByLabelText("1번 사람이 센 인원"), { target: { value: "64" } });
    await waitFor(() => expect(screen.getByText("20%")).toBeTruthy());      // 100 − 64 ÷ 80
    expect(screen.getByText("+2")).toBeTruthy();                           // AI 66 − 사람 64
    fireEvent.click(screen.getByText("4.7 정확도 판정"));
    await screen.findByText(/AI 가 평균 2\.0명 많이 셈/);
    const call = f.mock.calls.find(([u]) => String(u).endsWith("/v1/admin/verification-runs")) as unknown as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toEqual({ batch_id: 9, items: [{ seq: 1, manual_persons: 64 }] });
  });
});
