/* S10 권한 매트릭스 — 역할×기능 체크박스, 잠긴 칸, 변경 칸 수, 열 일괄 토글, 저장(PUT 본문) */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Rbac from "../src/pages/admin/Rbac";

const ROLES = [
  { role: "user", label: "일반 사용자", locked: false },
  { role: "controller", label: "관제 담당자", locked: false },
  { role: "admin", label: "운영 관리자", locked: true },
];
const VIEW = {
  roles: ROLES, changed_cells: 0, updated_at: null, updated_by: null,
  permissions: [
    { permission: "diagnose", label: "현재 프레임 진단 (UC1)", roles: ["user", "controller", "admin"], default_roles: ["user", "controller", "admin"], locked_roles: ["admin"] },
    { permission: "measure", label: "후속 차량 실측 등록 (UC10)", roles: ["controller", "admin"], default_roles: ["controller", "admin"], locked_roles: ["admin"] },
    { permission: "accounts", label: "계정 역할·정지", roles: ["admin"], default_roles: ["admin"], locked_roles: ["user", "controller", "admin"] },
  ],
};
const res = (body: unknown) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) }) as unknown as Response;

afterEach(() => vi.unstubAllGlobals());

describe("권한 매트릭스", () => {
  it("역할×기능 칸을 그리고, 잠긴 칸은 못 바꾼다", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(VIEW)));
    render(<Rbac />);
    const cell = await screen.findByLabelText("일반 사용자 — 현재 프레임 진단") as HTMLInputElement;
    expect(cell.checked).toBe(true);
    expect((screen.getByLabelText("일반 사용자 — 후속 차량 실측 등록") as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText("운영 관리자 — 현재 프레임 진단") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText("관제 담당자 — 계정 역할·정지") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByText("저장") as HTMLButtonElement).disabled).toBe(true);
  });

  it("칸을 바꾸면 변경 수가 보이고, 저장은 권한마다 허용 역할 전체를 PUT 한다", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => res(init?.method === "PUT"
      ? { ...VIEW, changed_cells: 1, permissions: VIEW.permissions.map((p) => p.permission === "measure" ? { ...p, roles: ["user", "controller", "admin"] } : p) }
      : VIEW));
    vi.stubGlobal("fetch", fetchMock);
    render(<Rbac />);
    fireEvent.click(await screen.findByLabelText("일반 사용자 — 후속 차량 실측 등록"));
    fireEvent.click(screen.getByText("저장 (1칸 변경)"));
    await waitFor(() => expect(screen.getByText(/기본값과 다른 칸 1개\)/)).toBeTruthy());
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "PUT")! as [string, RequestInit];
    expect(url).toContain("/v1/admin/rbac");
    expect(JSON.parse(init.body as string).permissions).toEqual({ diagnose: ["user", "controller", "admin"], measure: ["user", "controller", "admin"], accounts: ["admin"] });
  });

  it("열 머리를 누르면 그 역할의 잠기지 않은 칸을 모두 끄고 켠다, 되돌리기", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(VIEW)));
    render(<Rbac />);
    await screen.findByLabelText("관제 담당자 — 현재 프레임 진단");
    fireEvent.click(screen.getByTitle("관제 담당자 열 전체 켜기/끄기"));
    expect((screen.getByLabelText("관제 담당자 — 현재 프레임 진단") as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText("관제 담당자 — 후속 차량 실측 등록") as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText("저장 (2칸 변경)")).toBeTruthy();
    fireEvent.click(screen.getByText("되돌리기"));
    expect((screen.getByLabelText("관제 담당자 — 현재 프레임 진단") as HTMLInputElement).checked).toBe(true);
  });
});
