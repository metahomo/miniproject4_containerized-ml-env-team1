/* API 클라이언트 (T018) — 키 헤더, GateError 파싱, 2초 지연 표시(§15-3), 서버 무응답 처리.
   사이트는 로그인해야 쓴다(T108) — 모든 요청에 로그인 토큰(Bearer)을, 관리자 키로 로그인했으면 X-Admin-Key 를 붙인다.
   브라우저 빌드에는 어떤 키도 넣지 않는다. 서버가 세션·키를 거부하면 로그아웃 → 로그인 화면. */
import { getAdminKey, getToken, logout } from "../stores/auth";

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "";

/** 로그인 토큰 또는 (최초 설정용) 관리자 키 — 모든 요청에 */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  if (token) return { Authorization: `Bearer ${token}` };
  const adminKey = getAdminKey();
  return adminKey ? { "X-Admin-Key": adminKey } : {};
}

export interface GateError {
  gate: string;
  reason_code: string;
  reason: string;
  resolver_role: "self" | "operator" | "external" | "undefined";
  allowed_spec?: Record<string, unknown> | null;
  details?: Array<Record<string, unknown>> | null;
  gate_event_id?: number | null;
}

export class ApiError extends Error {
  status: number;
  gate?: GateError;
  offline = false;
  constructor(status: number, message: string, gate?: GateError) {
    super(message);
    this.status = status;
    this.gate = gate;
  }
}

export interface ReqOpts {
  admin?: boolean;   // 운영 관리자·관제 담당자 경로 (표시용 — 인증 헤더는 모든 요청에 같다)
  auth?: boolean;    // 로그인 계정 경로(/v1/auth/me·keys)
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | undefined>;
  onDelay?: (delayed: boolean) => void; // NFR-01: 2초 넘으면 "지연 중"
}

export async function api<T>(method: string, path: string, opts: ReqOpts = {}): Promise<T> {
  const url = new URL(API_BASE + path, window.location.origin);
  Object.entries(opts.query ?? {}).forEach(([k, v]) => v !== undefined && url.searchParams.set(k, String(v)));
  const headers: Record<string, string> = {};
  Object.assign(headers, authHeaders());
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const timer = opts.onDelay ? window.setTimeout(() => opts.onDelay?.(true), 2000) : undefined;
  let res: Response;
  try {
    res = await fetch(url.toString(), { method, headers, body });
  } catch (e) {
    const err = new ApiError(0, "진단 API 서버에 연결할 수 없다");
    err.offline = true;
    throw err;
  } finally {
    if (timer) window.clearTimeout(timer);
    opts.onDelay?.(false);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { detail: text };
  }
  if (!res.ok) {
    const j = json as Record<string, unknown>;
    if (j && typeof j.gate === "string") {
      if (j.gate === "G1" && (["SESSION_INVALID", "AUTH_MISSING"].includes(String(j.reason_code)) || (opts.admin && ["ADMIN_INVALID", "ADMIN_REQUIRED"].includes(String(j.reason_code))))) logout();   // 세션 만료·키 교체 → 로그인 화면
      throw new ApiError(res.status, String(j.reason), j as unknown as GateError);
    }
    const detail = j && j.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(-1)[0]}: ${d.msg}`).join(", ")
      : typeof detail === "string" ? detail : `HTTP ${res.status}`;
    throw new ApiError(res.status, msg, {
      gate: res.status === 422 ? "G2" : "—",
      reason_code: "VALIDATION",
      reason: msg,
      resolver_role: "self",
    });
  }
  return json as T;
}

/** 파일 내려받기 (샘플 사진·영상) — 키 헤더를 붙여 Blob 으로 받는다 */
export async function getBlob(path: string): Promise<Blob> {
  const headers = authHeaders();
  let res: Response;
  try {
    res = await fetch(new URL(API_BASE + path, window.location.origin).toString(), { headers });
  } catch {
    const err = new ApiError(0, "진단 API 서버에 연결할 수 없다");
    err.offline = true;
    throw err;
  }
  if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  return res.blob();
}

export const get = <T>(path: string, opts: ReqOpts = {}) => api<T>("GET", path, opts);
export const post = <T>(path: string, opts: ReqOpts = {}) => api<T>("POST", path, opts);
export const del = <T>(path: string, opts: ReqOpts = {}) => api<T>("DELETE", path, opts);
export const patch = <T>(path: string, opts: ReqOpts = {}) => api<T>("PATCH", path, opts);
export const put = <T>(path: string, opts: ReqOpts = {}) => api<T>("PUT", path, opts);

// 시각 — 서버는 UTC('YYYY-MM-DDTHH:MM:SS', Z 없음)로 주고받는다. 화면에 보이고 입력받는 것은 모두 한국 시각(KST, UTC+9)이다.
const KST_MS = 9 * 3600 * 1000;
const utcMs = (iso: string) => Date.parse(iso.replace("Z", "").slice(0, 19) + "Z");
/** 서버 UTC → 한국 시각 'YYYY-MM-DD HH:MM:SS' */
export const kst = (iso?: string | null) => {
  if (!iso) return "";
  const t = utcMs(iso);
  return isNaN(t) ? iso : new Date(t + KST_MS).toISOString().slice(0, 19).replace("T", " ");
};
export const fmtTime = (iso?: string | null) => (iso ? kst(iso) : "—");
/** 한국 시각 'HH:MM' (초까지면 withSec) */
export const hhmm = (iso?: string | null, withSec = false) => (iso ? kst(iso).slice(11, withSec ? 19 : 16) : "—");
/** 한국 시각 날짜 'YYYY-MM-DD' */
export const kstDate = (iso?: string | null) => (iso ? kst(iso).slice(0, 10) : "—");
/** 입력칸 값(한국 시각 'YYYY-MM-DDTHH:MM[:SS]') → 서버로 보낼 UTC ISO. 비었거나 형식이 틀리면 그대로 */
export const kstInputToUtc = (v: string) => {
  const m = v.trim().replace(" ", "T");
  if (!m) return "";
  const t = Date.parse((m.length === 16 ? m + ":00" : m.slice(0, 19)) + "Z");
  return isNaN(t) ? v : new Date(t - KST_MS).toISOString().slice(0, 19);
};
/** 지금(또는 ms 뒤) 한국 시각 입력칸 값 'YYYY-MM-DDTHH:MM:SS' */
export const kstNowInput = (plusMs = 0) => new Date(Date.now() + plusMs + KST_MS).toISOString().slice(0, 19);
export const minutesFromNow = (iso?: string | null) => {
  if (!iso) return null;
  const t = Date.parse(iso + "Z");
  return Math.round((t - Date.now()) / 60000);
};
export const minutesAgo = (iso?: string | null) => {
  const m = minutesFromNow(iso);
  return m === null ? null : -m;
};
