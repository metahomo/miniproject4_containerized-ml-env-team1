/* T109 — 버스 조회: 버스 번호를 누르면 그 노선의 정류장만, 정류장을 누르면 그 정류장에 서는 버스 번호만 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import NextVehicle, { stopKey } from "../src/pages/NextVehicle";

const R = (id: string, no: string) => ({ route_id: id, route_name: `${no} (${id})`, route_no: no, mode: "bus" });
const S = (id: string, rid: string, no: string, name: string) => ({ stop_id: id, route_id: rid, route_name: `${no} (${rid})`, route_no: no, stop_name: name });
const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }) as unknown as Response;
function api(url: string) {
  const u = new URL(url, "http://x");
  Object.defineProperty(u, "pathname", { value: decodeURIComponent(u.pathname) });
  if (u.pathname === "/v1/readiness") return json({ readiness: "ready" });
  if (u.pathname === "/v1/reference/routes") return json([R("1", "102번"), R("2", "15번"), R("3", "7번")]);
  if (u.pathname === "/v1/reference/stops/1:900/routes") return json([S("2:900", "2", "15번", "시청 (A 방면)"), S("1:900", "1", "102번", "시청 (A 방면)")]);
  if (u.pathname === "/v1/reference/stops" && u.searchParams.get("route_id") === "1") return json([S("1:900", "1", "102번", "시청 (A 방면)"), S("1:950", "1", "102번", "대전역")]);
  if (u.pathname === "/v1/reference/stops" && u.searchParams.get("q")) return json([S("1:900", "1", "102번", "시청 (A 방면)"), S("2:900", "2", "15번", "시청 (A 방면)"), S("3:901", "3", "7번", "시청 (B 방면)")]);
  return json([]);
}
afterEach(() => vi.unstubAllGlobals());

describe("버스 조회 — 버스 번호 ↔ 정류장 서로 거르기", () => {
  it("같은 정류장인지는 정류소 ID(노선ID:정류소ID 의 뒤)로, 없으면 이름으로", () => {
    expect(stopKey({ stop_id: "30300037:42620", stop_name: "충남대학교" })).toBe("42620");
    expect(stopKey({ stop_id: "3001", stop_name: "충남대" })).toBe("충남대");
  });

  it("노선을 고르면 그 노선의 정류장만, 정류장을 먼저 고르면 그 정류장에 서는 노선만 고를 수 있다", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => api(url)));
    render(<MemoryRouter initialEntries={["/next-vehicle?q=시청"]}><NextVehicle /></MemoryRouter>);
    const opts = (label: string) => Array.from((screen.getByLabelText(label) as HTMLSelectElement).options).map((o) => o.textContent ?? "").filter((t) => !/선택/.test(t));
    // 처음: 노선 전체 3개, 정류장은 이름 검색 결과를 정류소별로 하나씩 (시청 A 에는 버스 2개)
    await waitFor(() => expect(opts("노선")).toEqual(["102번", "15번", "7번"]));
    await waitFor(() => expect(opts("정류장")).toEqual(["시청 (A 방면) · 버스 2개", "시청 (B 방면) · 버스 1개"]));
    expect(screen.getByText("조회").closest("button")?.disabled).toBe(true);
    // 정류장을 먼저 고르면 → 노선은 그 정류장에 서는 것(15·102)만, 7번은 없다
    fireEvent.change(screen.getByLabelText("정류장"), { target: { value: "1:900" } });
    await waitFor(() => expect(opts("노선")).toEqual(["15번", "102번"]));
    // 노선을 고르면 → 정류장은 그 노선의 정류장만 (대전역 있음, 시청 B 없음) + 조회 가능
    fireEvent.change(screen.getByLabelText("노선"), { target: { value: "1" } });
    await waitFor(() => expect(opts("정류장")).toEqual(["시청 (A 방면)", "대전역"]));
    expect((screen.getByLabelText("정류장") as HTMLSelectElement).value).toBe("1:900");
    await waitFor(() => expect(screen.getByText("조회").closest("button")?.disabled).toBe(false));
    // 정류장 선택을 풀면 노선은 다시 전체
    fireEvent.change(screen.getByLabelText("정류장"), { target: { value: "" } });
    await waitFor(() => expect(opts("노선")).toEqual(["102번", "15번", "7번"]));
  });
});
