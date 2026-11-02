/* RBAC T107·T108 (+T095 관리자 키) — 로그인 화면(사이트 진입), 역할별 화면 게이트(G1), 아이디·비밀번호 로그인(Bearer), 관리자 키 로그인, 역할별 메뉴, 로그아웃 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";
import { afterEach, describe, expect, it, vi } from "vitest";
import { get } from "../src/api/client";
import { AdminGate, PermGate } from "../src/components/AdminLogin";
import { Sidebar } from "../src/layout/Sidebar";
import { getAdminKey, getPerms, getRole, getToken, login, loginPassword, logout } from "../src/stores/auth";

const res = (body: unknown, ok = true, status = ok ? 200 : 401) =>
  ({ ok, status, json: async () => body, text: async () => JSON.stringify(body) }) as unknown as Response;
const whoami = (role: "admin" | "user", ok = true) => vi.fn(async () => res({ caller_id: role === "admin" ? "op1" : "web", role }, ok));
const loginOk = (role: string) => vi.fn(async (url: string) =>
  url.endsWith("/v1/auth/login") ? res({ token: "tok-1", expires_at: "2026-09-30T00:00:00Z", account: { login_id: "u1", name: "홍길동", role } }) : res({}));
const R = ({ children }: { children: React.ReactNode }) => <MemoryRouter>{children}</MemoryRouter>;

afterEach(() => { act(() => logout()); vi.unstubAllGlobals(); });

describe("관리자 키 로그인 (최초 설정용)", () => {
  it("서버가 admin 으로 확인한 키만 저장한다", async () => {
    vi.stubGlobal("fetch", whoami("user"));
    expect((await login("wrong")).ok).toBe(false);
    expect(getAdminKey()).toBeNull();
    vi.stubGlobal("fetch", whoami("admin"));
    expect((await login("right-key")).ok).toBe(true);
    expect(getAdminKey()).toBe("right-key");
    expect(getRole()).toBe("admin");
    const [, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Admin-Key"]).toBe("right-key");
  });

  it("관리 화면은 로그인 전 G1 차단 + 폼, 관리자 키로 열고, 로그아웃하면 다시 차단", async () => {
    vi.stubGlobal("fetch", whoami("admin"));
    render(<R><AdminGate><p>관리 화면 본문</p></AdminGate></R>);
    expect(screen.getByText(/차단 상태 —/)).toBeTruthy();   // 로그인 전(이용자)에는 게이트 번호 없이
    expect(screen.queryByText("관리 화면 본문")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "관리자 키" }));
    fireEvent.change(screen.getByLabelText("관리자 키"), { target: { value: "right-key" } });
    fireEvent.click(screen.getByText("로그인"));
    await waitFor(() => expect(screen.getByText("관리 화면 본문")).toBeTruthy());
    act(() => logout());
    expect(screen.getByText(/차단 상태 —/)).toBeTruthy();
  });
});

describe("아이디·비밀번호 로그인 (RBAC)", () => {
  it("로그인하면 토큰·역할을 저장하고 모든 요청에 Bearer 를 붙인다 (빌드에 든 키 없음)", async () => {
    vi.stubGlobal("fetch", loginOk("controller"));
    expect((await loginPassword("u1", "pw-12345678")).ok).toBe(true);
    expect(getToken()).toBe("tok-1");
    expect(getRole()).toBe("controller");
    const f = vi.fn(async () => res([]));
    vi.stubGlobal("fetch", f);
    await get("/v1/admin/gate-events", { admin: true });
    await get("/v1/reference/cameras");
    const h = (i: number) => (f.mock.calls[i] as unknown as [string, RequestInit])[1].headers as Record<string, string>;
    expect(h(0).Authorization).toBe("Bearer tok-1");
    expect(h(1).Authorization).toBe("Bearer tok-1");   // 기본 기능도 로그인 토큰으로
    expect(h(1)["X-API-Key"]).toBeUndefined();
  });

  it("승인 대기 계정은 사유를 보이고 저장하지 않는다", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res({ gate: "G1", reason_code: "ACCOUNT_PENDING", reason: "운영 관리자 승인 대기 중" }, false, 403)));
    const r = await loginPassword("u1", "pw-12345678");
    expect(r.ok).toBe(false);
    expect(r.reason).toMatch(/승인 대기/);
    expect(getToken()).toBeNull();
  });

  it("세션이 만료되면(SESSION_INVALID) 자동 로그아웃한다", async () => {
    vi.stubGlobal("fetch", loginOk("admin"));
    await loginPassword("u1", "pw-12345678");
    vi.stubGlobal("fetch", vi.fn(async () => res({ gate: "G1", reason_code: "SESSION_INVALID", reason: "만료", resolver_role: "self" }, false, 401)));
    await expect(get("/v1/admin/policies/threshold", { admin: true })).rejects.toThrow();
    expect(getRole()).toBeNull();
  });

  it("권한 게이트: 관제 담당자는 관제 화면을 열고 운영 관리자 화면은 차단", async () => {
    vi.stubGlobal("fetch", loginOk("controller"));
    render(<R><PermGate perm="control_view"><p>관제 본문</p></PermGate><AdminGate><p>관리 본문</p></AdminGate></R>);
    expect(screen.queryByText("관제 본문")).toBeNull();
    await act(async () => { await loginPassword("u1", "pw-12345678"); });
    expect(screen.getByText("관제 본문")).toBeTruthy();
    expect(screen.queryByText("관리 본문")).toBeNull();
    expect(screen.getByText(/지금 로그인: 홍길동 \(관제 담당자\)/)).toBeTruthy();
  });
});

describe("사이트 진입 = 로그인 화면 (T108)", () => {
  it("로그인 전에는 어느 주소든 로그인 화면, /signup 은 회원가입", () => {
    const { unmount } = render(<MemoryRouter initialEntries={["/next-vehicle"]}><App /></MemoryRouter>);
    expect(screen.getByLabelText("로그인 화면")).toBeTruthy();
    expect(screen.queryByText("버스 조회")).toBeNull();
    unmount();
    render(<MemoryRouter initialEntries={["/signup"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "회원가입" })).toBeTruthy();
  });
});

describe("권한 매트릭스 기준 메뉴·게이트 (T110)", () => {
  const nav = (perms: string[]) => render(<R><Sidebar collapsed={false} onToggle={() => undefined} perms={perms} /></R>);
  const USER = ["diagnose", "next_vehicle", "reference_read", "api_guide", "own_keys"];
  const CONTROLLER = ["diagnose", "next_vehicle", "reference_read", "measure", "api_guide", "control_view"];
  it("일반 사용자 기본값: 기본 기능 + API 키, 관제·운영 관리 구역 없음", () => {
    nav(USER);
    expect(screen.getByText("버스 조회")).toBeTruthy();
    expect(screen.getByText("API 키")).toBeTruthy();
    expect(screen.queryByText("관제 뷰")).toBeNull();
    expect(screen.queryByText("후속 차량 실측 등록")).toBeNull();   // 기본값: 일반 사용자는 실측 등록 불가 (서버 403 과 같다)
    expect(screen.queryByText("관제")).toBeNull();
    expect(screen.queryByText("진단 정책 설정")).toBeNull();
  });
  it("관제 담당자 기본값: 카메라 현황·실측 등록 (관제 뷰 화면은 삭제됨)", () => {
    nav(CONTROLLER);
    expect(screen.queryByText("관제 뷰")).toBeNull();
    expect(screen.getByText("카메라 현황")).toBeTruthy();
    expect(screen.getByText("후속 차량 실측 등록")).toBeTruthy();
    expect(screen.queryByText("API 키")).toBeNull();
    expect(screen.queryByText("진단 정책 설정")).toBeNull();
  });
  it("운영 관리자: 운영 관리 메뉴 + 계정·키 관리, 카메라는 «전원 관리»", () => {
    nav(["diagnose", "next_vehicle", "reference_read", "measure", "api_guide", "own_keys", "control_view", "admin", "accounts"]);
    expect(screen.getByText("진단 정책 설정")).toBeTruthy();
    expect(screen.getByText("계정 · 키 관리")).toBeTruthy();
    expect(screen.getByText("카메라 전원 관리")).toBeTruthy();
  });
  it("매트릭스에서 바꾼 칸이 메뉴에 그대로 — 일반 사용자에 실측 등록을 켜고 버스 조회를 끄면", () => {
    nav([...USER.filter((p) => p !== "next_vehicle"), "measure"]);
    expect(screen.getByText("후속 차량 실측 등록")).toBeTruthy();
    expect(screen.queryByText("버스 조회")).toBeNull();
    expect(screen.queryByText("관제 뷰")).toBeNull();
  });
  it("로그인하면 whoami 의 유효 권한을 받아 게이트가 따른다 (역할 기본값보다 우선)", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/v1/auth/login")
      ? res({ token: "tok-1", account: { login_id: "u1", name: "홍길동", role: "user" } })
      : res({ role: "user", permissions: ["diagnose", "measure"] })));
    render(<R><PermGate perm="measure"><p>실측 본문</p></PermGate><PermGate perm="own_keys"><p>키 본문</p></PermGate></R>);
    await act(async () => { await loginPassword("u1", "pw-12345678"); });
    expect(getPerms()).toEqual(["diagnose", "measure"]);
    expect(screen.getByText("실측 본문")).toBeTruthy();
    expect(screen.queryByText("키 본문")).toBeNull();
    expect(screen.getByText(/«API 키» 권한이 있어야/)).toBeTruthy();
  });
  it("권한을 받기 전(서버 무응답)에는 역할 기본값", async () => {
    vi.stubGlobal("fetch", loginOk("controller"));
    await loginPassword("u1", "pw-12345678");
    expect(getPerms()).toContain("control_view");
    expect(getPerms()).not.toContain("own_keys");
  });
});

describe("홈 = 버스 조회 (2026-09-30 홈 단순화)", () => {
  const api = (role: string) => vi.fn(async (url: string) =>
    url.endsWith("/v1/auth/login") ? res({ token: "tok-1", account: { login_id: "u1", name: "홍길동", role } })
    : url.endsWith("/v1/readiness") ? res({ readiness: "ready" }) : res([]));
  it("일반 사용자: 로그인하면 사이드바 없이 버스 조회가 바로 — 메뉴는 «API 키» 하나, 진단·홈 버튼 없음", async () => {
    vi.stubGlobal("fetch", api("user"));
    await act(async () => { await loginPassword("u1", "pw-12345678"); });
    render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "버스 조회" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "API 키" })).toBeTruthy();
    expect(screen.queryByText("현재 프레임 진단")).toBeNull();
    expect(screen.queryByText("관제")).toBeNull();
    expect(document.querySelector(".sidebar")).toBeNull();
  });
  it("일반 사용자: «API 키» 는 키 신청과 3단계 사용법", async () => {
    vi.stubGlobal("fetch", api("user"));
    await act(async () => { await loginPassword("u1", "pw-12345678"); });
    render(<MemoryRouter initialEntries={["/my/keys"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "사용법" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "신청" })).toBeTruthy();
    expect(screen.getByLabelText("호출 예").textContent).toContain("X-API-Key");
  });
  it("옛 주소 /next-vehicle 은 홈으로, 관제 담당자는 사이드바 + 홈 = 버스 조회", async () => {
    vi.stubGlobal("fetch", api("controller"));
    await act(async () => { await loginPassword("u1", "pw-12345678"); });
    render(<MemoryRouter initialEntries={["/next-vehicle"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "버스 조회" })).toBeTruthy();
    expect(document.querySelector(".sidebar")).toBeTruthy();
    expect(screen.queryByText("API 문서 (가이드·매뉴얼)")).toBeNull();   // 긴 API 문서는 운영 관리자 메뉴
  });
});
