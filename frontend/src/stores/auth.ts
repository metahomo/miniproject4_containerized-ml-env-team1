/* 로그인·역할 (RBAC, T107·T108 — 역할은 유스케이스 액터). 이 브라우저에만 저장한다.
   - 사이트는 로그인해야 쓴다. 아이디·비밀번호 로그인 → Bearer 토큰 + 계정 역할
     (user 일반 사용자 · controller 관제 담당자 · admin 운영 관리자). 회원가입하면 바로 일반 사용자.
   - 관리자 키 로그인(T095) → 최초 운영 관리자 (계정을 만들기 전 설정용)
   서버가 토큰·키를 거부하면(만료·정지·교체) 자동으로 로그아웃한다.
   - 메뉴·화면 게이트는 역할이 아니라 유효 권한(권한 매트릭스 S10, T110)을 따른다 — 로그인·창 복귀·매트릭스 저장 때 /v1/auth/whoami 로 새로 받는다. */
import { useSyncExternalStore } from "react";

export type Role = "admin" | "controller" | "user";
export interface AuthAccount { login_id: string; name: string; role: Role }
interface AuthState { token?: string; adminKey?: string; account?: AuthAccount; permissions?: string[] }

/** 권한 (backend rbac.PERMISSIONS) — 화면 게이트 문구용 이름 */
export type Perm = "diagnose" | "next_vehicle" | "reference_read" | "measure" | "api_guide" | "own_keys" | "control_view" | "admin" | "accounts";
export const PERM_LABEL: Record<Perm, string> = {
  diagnose: "현재 프레임 진단", next_vehicle: "버스 조회", reference_read: "기준 정보 보기", measure: "후속 차량 실측 등록",
  api_guide: "API 문서", own_keys: "API 키", control_view: "관제 · 카메라 현황", admin: "운영 관리", accounts: "계정 · 키 관리",
};
/* 서버에서 권한을 받기 전(첫 화면·서버 무응답)에만 쓰는 역할별 기본값 — rbac.PERMISSIONS 기본값과 같다 */
const ALL: Perm[] = ["diagnose", "next_vehicle", "reference_read", "measure", "api_guide", "own_keys", "control_view", "admin", "accounts"];
const DEFAULT_PERMS: Record<Role, Perm[]> = {
  user: ["diagnose", "next_vehicle", "reference_read", "api_guide", "own_keys"],
  controller: ["diagnose", "next_vehicle", "reference_read", "measure", "api_guide", "control_view"],
  admin: ALL,
};

const STORE = "cv.auth";
const OLD_STORE = "cv.adminKey";   // T095 — 관리자 키만 저장하던 형식
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "";
export const ROLE_LABEL: Record<Role, string> = { admin: "운영 관리자", controller: "관제 담당자", user: "일반 사용자" };

function read(): AuthState {
  try {
    const s = localStorage.getItem(STORE);
    if (s) return JSON.parse(s) as AuthState;
    const k = localStorage.getItem(OLD_STORE);
    if (k) return { adminKey: k, account: { login_id: "admin-key", name: "운영 관리자(관리자 키)", role: "admin" } };
  } catch { /* 저장소를 못 쓰면 로그인 안 된 상태 */ }
  return {};
}
let state: AuthState = read();
const listeners = new Set<() => void>();
function save(next: AuthState) {
  state = next;
  try {
    if (next.account) localStorage.setItem(STORE, JSON.stringify(next)); else localStorage.removeItem(STORE);
    localStorage.removeItem(OLD_STORE);
  } catch { /* 이 탭에서만 유지 */ }
  listeners.forEach((l) => l());
}

export const getToken = () => state.token ?? null;
export const getAdminKey = () => state.adminKey ?? null;
export const getAccount = () => state.account ?? null;
export const getRole = (): Role | null => state.account?.role ?? null;
export const isAdmin = () => getRole() === "admin";
export const hasRole = (...roles: Role[]) => { const r = getRole(); return !!r && roles.includes(r); };
const NO_PERMS: string[] = [];
/** 유효 권한 — 서버에서 받은 값, 아직 없으면 역할 기본값 */
export const getPerms = (): string[] => {
  const r = getRole();
  if (!r) return NO_PERMS;
  return state.permissions ?? DEFAULT_PERMS[r];
};
export const hasPerm = (p: Perm) => getPerms().includes(p);
/** 관제·운영 권한이 하나라도 있으면 사이드바 대시보드, 없으면 «버스 조회 + API 키» 만 있는 간단한 화면 (2026-09-30) */
const STAFF: Perm[] = ["control_view", "measure", "admin", "accounts"];
export const isStaff = (perms: string[]) => STAFF.some((p) => perms.includes(p));

/** 유효 권한을 서버(/v1/auth/whoami)에서 다시 받는다. 실패하면 가지고 있던 값을 그대로 둔다 */
export async function refreshPerms(): Promise<void> {
  const cur = state;
  const h: Record<string, string> = cur.token ? { Authorization: `Bearer ${cur.token}` } : cur.adminKey ? { "X-Admin-Key": cur.adminKey } : {};
  if (!cur.account || !Object.keys(h).length) return;
  try {
    const res = await fetch(`${API_BASE}/v1/auth/whoami`, { headers: h });
    if (!res.ok) return;
    const j = await res.json().catch(() => ({}));
    if (state !== cur || !Array.isArray(j.permissions)) return;   // 그사이 로그아웃·다른 계정 로그인
    if (JSON.stringify(j.permissions) !== JSON.stringify(cur.permissions)) save({ ...cur, permissions: j.permissions });
  } catch { /* 서버 무응답 — 가지고 있던 권한 유지 */ }
}

export function logout(): void {
  const t = state.token;
  if (t) fetch(`${API_BASE}/v1/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${t}` } }).catch(() => undefined);
  save({});
}

/** 아이디·비밀번호 로그인 */
export async function loginPassword(login_id: string, password: string): Promise<{ ok: boolean; reason?: string }> {
  if (!login_id.trim() || !password) return { ok: false, reason: "아이디와 비밀번호를 입력한다" };
  try {
    const res = await fetch(`${API_BASE}/v1/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ login_id: login_id.trim(), password }) });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, reason: j.reason ?? "로그인 실패" };
    save({ token: j.token, account: { login_id: j.account.login_id, name: j.account.name, role: j.account.role } });
    await refreshPerms();
    return { ok: true };
  } catch {
    return { ok: false, reason: "서버에 연결할 수 없다" };
  }
}

/** 관리자 키 로그인 (최초 설정용, T095) — 서버가 admin 으로 확인한 키만 저장 */
export async function login(key: string): Promise<{ ok: boolean; reason?: string }> {
  const k = key.trim();
  if (!k) return { ok: false, reason: "관리자 키를 입력한다" };
  try {
    const res = await fetch(`${API_BASE}/v1/auth/whoami`, { headers: { "X-Admin-Key": k } });
    const j = await res.json().catch(() => ({}));
    if (!res.ok || j.role !== "admin") return { ok: false, reason: "관리자 키가 맞지 않는다" };
    save({ adminKey: k, account: { login_id: "admin-key", name: "운영 관리자(관리자 키)", role: "admin" },
           permissions: Array.isArray(j.permissions) ? j.permissions : undefined });
  } catch {
    return { ok: false, reason: "서버에 연결할 수 없다" };
  }
  return { ok: true };
}

const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
export function useAuth(): AuthAccount | null {
  return useSyncExternalStore(subscribe, getAccount, getAccount);
}
/** 관리 버튼 표시 — 권한 매트릭스의 «운영 관리» 권한 기준(2026-09-30, 메뉴·화면 게이트와 같은 기준). 이 행은 잠겨 있어 운영 관리자만 가진다 */
const canAdmin = () => hasPerm("admin");
export function useAdmin(): boolean {
  return useSyncExternalStore(subscribe, canAdmin, canAdmin);
}
export function useRole(): Role | null {
  return useSyncExternalStore(subscribe, getRole, getRole);
}
export function usePerms(): string[] {
  return useSyncExternalStore(subscribe, getPerms, getPerms);
}
/** 설계 번호(UC·S·G·FR·SC·R …)를 화면에 보일지 — 사용자 요청(2026-09-30)으로 모두에게 숨긴다.
    true 로 바꾸면 운영 관리자에게만 다시 보인다. */
export const SHOW_DESIGN_CODES = false;
/** 역할과 무관한 곳(모듈 수준 문구)용 */
export const designCode = (t: string) => (SHOW_DESIGN_CODES ? t : "");
/** c(" (G0)") 처럼 감싸면 번호를 보일 때만 그 글자를 돌려준다 */
export function useCodes(): (t: string) => string {
  const show = SHOW_DESIGN_CODES && usePerms().includes("admin");
  return (t: string) => (show ? t : "");
}
