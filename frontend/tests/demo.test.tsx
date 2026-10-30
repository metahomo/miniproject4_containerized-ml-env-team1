/* S8 시연 모드 켜기 — 시연 모드만 바꾸고 유효 시간 규칙(S3 3.3)의 나머지 값은 현재 판본 그대로 보낸다 (2026-09-30) */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Demo from "../src/pages/admin/Demo";

const res = (body: unknown) => ({ ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }) as unknown as Response;
const POLICY = { factor: 0.8, cap_minutes: 25, default_minutes: 12, window_minutes: 2, demo_on: false, demo_end_at: null,
  route_exceptions: [{ route_id: "30300037", minutes: 12 }, { route_id: "30300001", minutes: 7 }] };

afterEach(() => vi.unstubAllGlobals());

describe("시연 준비 — 시연 모드만 바꾼다", () => {
  it("켜기는 현재 계수·상한·기본값·합산 창·노선별 예외를 그대로 두고 demo_on 만 바꾼다", async () => {
    const f = vi.fn(async (url: string, _init?: RequestInit) =>
      url.includes("/v1/admin/mappings") ? res([{ camera_id: "CAM-DEMO-01", vehicle_id: "대전75자1001" }, { camera_id: "CAM-DEMO-02", vehicle_id: "대전75자1002" }])
        : url.includes("/v1/admin/policies/validity") ? res({ policy: POLICY, preview: [] })
        : res({ demo_on: false, readiness: { readiness: "ready" }, roi_stale_cameras: [], expired_measurements_today: 0 }));
    vi.stubGlobal("fetch", f);
    render(<MemoryRouter><Demo /></MemoryRouter>);
    const btn = await screen.findByText("시연 모드 켜기") as HTMLButtonElement;
    await waitFor(() => expect(btn.disabled).toBe(false));
    fireEvent.click(btn);
    await waitFor(() => expect(f.mock.calls.some(([u, i]) => String(u).endsWith("/v1/admin/policies/validity") && (i as RequestInit | undefined)?.method === "POST")).toBe(true));
    const [, init] = f.mock.calls.find(([u, i]) => String(u).endsWith("/v1/admin/policies/validity") && (i as RequestInit | undefined)?.method === "POST") as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ factor: 0.8, cap_minutes: 25, default_minutes: 12, window_minutes: 2, route_exceptions: POLICY.route_exceptions, demo_on: true, demo_end_at: null });
  });
});
