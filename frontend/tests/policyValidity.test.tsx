/* S3 3.3 혼잡도 유효 시간 — 버스 번호 표시, 5개만 보이고 펼치기, 예외를 버스 번호로 입력 (2026-09-30) */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Policy from "../src/pages/admin/Policy";

const res = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) }) as unknown as Response;
const preview = [
  ...Array.from({ length: 7 }, (_, i) => ({ route_id: `R${i}`, route_name: `${(i + 1) * 100}번 · 간선 · 가↔나${i} (R${i})`, headway_minutes: 10 + i, validity_minutes: 10 + i, validity_source: "bis" })),
  { route_id: "30300099", route_name: "700번 · 다↔라 (30300099)", headway_minutes: 9, validity_minutes: 9, validity_source: "bis" },   // 같은 번호 두 노선
  { route_id: "30300037", route_name: "102번 · 간선 · 수통골기점지↔대전역/역전시장 (30300037)", headway_minutes: 15, validity_minutes: 12, validity_source: "exception" },
];
const VIEW = { policy: { factor: 1, cap_minutes: 30, default_minutes: 10, window_minutes: 1, demo_on: false, route_exceptions: [{ route_id: "30300037", minutes: 12 }] }, preview };

afterEach(() => vi.unstubAllGlobals());

function setup() {
  const f = vi.fn(async (url: string, init?: RequestInit) =>
    url.includes("/v1/admin/policies/validity") ? res(init?.method === "POST" ? VIEW : VIEW, init?.method === "POST" ? 201 : 200)
      : url.includes("/v1/admin/policies/threshold") ? res([])
      : url.includes("/v1/reference/threshold") ? res({ free_min_ratio: 50, crowded_max_ratio: 20, count_conf_min_effective: 0.2 })
      : res({}));
  vi.stubGlobal("fetch", f);
  render(<MemoryRouter><Policy /></MemoryRouter>);
  return f;
}

describe("3.3 혼잡도 유효 시간", () => {
  it("버스 번호로 보이고, 예외 노선이 먼저, 처음엔 5개만 — 펼치면 전부", async () => {
    setup();
    expect(await screen.findByText("102번 · 간선 · 수통골기점지↔대전역/역전시장")).toBeTruthy();                        // 예외 노선이 맨 위
    expect(screen.getByText("노선별 예외")).toBeTruthy();
    expect(screen.queryByText(/^600번/)).toBeNull();                               // 6번째부터 접힘
    fireEvent.click(screen.getByText("전체 보기 (9개 노선)"));
    expect(screen.getAllByText(/^700번/)).toHaveLength(2);
    expect((screen.getByLabelText(/노선별 예외/) as HTMLInputElement).value).toBe("102번:12");   // 입력도 버스 번호로
  });
  it("예외를 버스 번호로 넣으면 노선 ID 로 바꿔 저장, 모르는 번호는 저장하지 않는다", async () => {
    const f = setup();
    const input = await screen.findByLabelText(/노선별 예외/) as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe("102번:12"));
    fireEvent.change(input, { target: { value: "999:5" } });
    fireEvent.click(screen.getByText("규칙 저장"));
    expect(await screen.findByText(/모르는 버스 번호다/)).toBeTruthy();
    fireEvent.change(input, { target: { value: "700:5" } });
    fireEvent.click(screen.getByText("규칙 저장"));
    expect(await screen.findByText(/같은 번호의 노선이 2개다/)).toBeTruthy();
    fireEvent.change(input, { target: { value: "102:12, 300번:8" } });
    fireEvent.click(screen.getByText("규칙 저장"));
    await waitFor(() => expect(f.mock.calls.some(([u, i]) => String(u).includes("/policies/validity") && (i as RequestInit | undefined)?.method === "POST")).toBe(true));
    const [, init] = f.mock.calls.find(([u, i]) => String(u).includes("/policies/validity") && (i as RequestInit | undefined)?.method === "POST") as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body)).route_exceptions).toEqual([{ route_id: "30300037", minutes: 12 }, { route_id: "R2", minutes: 8 }]);
  });
});
