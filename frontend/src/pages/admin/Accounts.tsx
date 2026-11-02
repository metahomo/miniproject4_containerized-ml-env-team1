/* 계정·키 관리 (RBAC T107·T108, 운영 관리자) — API 키 승인·반려, 역할 부여(일반 사용자·관제 담당자·운영 관리자), 정지, 계정 만들기, 키 폐기.
   회원가입은 바로 일반 사용자라 계정 승인은 없다. 정지·역할 변경은 그 계정의 로그인 세션을 끊고, 정지 계정의 키는 거부된다. */
import { useCallback, useEffect, useState } from "react";
import { ApiError, del, fmtTime, get, patch, post, type GateError } from "../../api/client";
import { GateBlock } from "../../components/GateBlock";
import { ROLE_LABEL, type Role } from "../../stores/auth";

interface Account { account_id: number; login_id: string; name: string; org: string | null; email: string | null; role: Role; status: "pending" | "active" | "disabled";
  created_at: string; approved_at: string | null; approved_by: string | null; last_login_at: string | null; active_keys: number }
interface ApiKey { key_id: number; account_id: number; login_id: string; account_name: string; org: string | null; name: string; key_prefix: string;
  status: "pending" | "active" | "rejected"; created_at: string; approved_at: string | null; approved_by: string | null; last_used_at: string | null; revoked_at: string | null }
const KEY_STATE = (k: ApiKey) => k.revoked_at ? <span className="muted">폐기 {fmtTime(k.revoked_at)}</span>
  : k.status === "pending" ? <b style={{ color: "var(--status-normal)" }}>승인 대기</b>
  : k.status === "rejected" ? <span style={{ color: "var(--status-crowded)" }}>반려</span> : <span>사용 중 · 승인 {k.approved_by ?? "—"}</span>;

const STATUS: Record<Account["status"], string> = { pending: "승인 대기", active: "사용 중", disabled: "정지" };
const ROLES: Role[] = ["user", "controller", "admin"];
interface Change { change_id: number; field: "role" | "status"; old_value: string | null; new_value: string; changed_at: string; changed_by: string }
const changeText = (c: Change) => {
  const v = (x: string | null) => (x == null ? "—" : c.field === "role" ? ROLE_LABEL[x as Role] ?? x : STATUS[x as Account["status"]] ?? x);
  return `${c.field === "role" ? "역할" : "상태"} ${v(c.old_value)} → ${v(c.new_value)}`;
};

export default function Accounts() {
  const [accs, setAccs] = useState<Account[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [gate, setGate] = useState<GateError | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [hist, setHist] = useState<{ acc: Account; rows: Change[] } | null>(null);   // 역할·상태 변경 이력 (2026-09-30)
  const showHist = (a: Account) => get<Change[]>(`/v1/admin/accounts/${a.account_id}/changes`, { admin: true }).then((rows) => setHist({ acc: a, rows })).catch(fail);
  const [nc, setNc] = useState({ login_id: "", name: "", password: "", role: "controller" as Role, org: "" });
  const fail = (err: unknown) => setGate(err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" });
  const load = useCallback(() => {
    get<Account[]>("/v1/admin/accounts", { admin: true }).then(setAccs).catch(fail);
    get<ApiKey[]>("/v1/admin/api-keys", { admin: true }).then(setKeys).catch(fail);
  }, []);
  useEffect(() => { load(); }, [load]);
  const run = async (f: () => Promise<unknown>, done: string) => { setGate(null); setMsg(null); try { await f(); setMsg(done); load(); } catch (err) { fail(err); } };
  const update = (a: Account, body: Partial<Pick<Account, "role" | "status">>, done: string) => run(() => patch(`/v1/admin/accounts/${a.account_id}`, { admin: true, body }), done);
  const create = (e: React.FormEvent) => { e.preventDefault(); run(() => post("/v1/admin/accounts", { admin: true, body: { ...nc, org: nc.org.trim() || null } }), `${nc.login_id} 계정을 만들었다 (${ROLE_LABEL[nc.role]}, 바로 사용)`).then(() => setNc({ ...nc, login_id: "", name: "", password: "", org: "" })); };
  const pending = keys.filter((k) => k.status === "pending" && !k.revoked_at);
  const review = (k: ApiKey, status: "active" | "rejected") =>
    run(() => patch(`/v1/admin/api-keys/${k.key_id}`, { admin: true, body: { status } }), `${k.login_id} «${k.name}» 키 ${status === "active" ? "승인 — 바로 쓸 수 있다" : "반려"}`);
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">계정 · 키 관리</h1>
        <p className="t-caption">역할은 유스케이스 액터다 — 일반 사용자(가입 즉시: 기본 기능·API 키 신청) · 관제 담당자(카메라 현황 읽기·실측 등록) · 운영 관리자(모든 관리). 사이트는 로그인해야 쓴다</p></div>
      {msg && <div className="toast" role="status">{msg}</div>}
      <section className="utility-card stack" aria-label="API 키 승인 대기">
        <h3 className="t-body-strong">API 키 승인 대기 ({pending.length})</h3>
        {pending.length === 0 ? <p className="t-caption muted">승인을 기다리는 키 신청이 없다</p> : (
          <table><thead><tr><th>신청자</th><th>소속</th><th>연계 시스템 (키 이름)</th><th>앞자리</th><th>신청</th><th /></tr></thead><tbody>
            {pending.map((k) => (
              <tr key={k.key_id}><td>{k.account_name} ({k.login_id})</td><td>{k.org ?? "—"}</td><td>{k.name}</td><td><code>{k.key_prefix}…</code></td><td>{fmtTime(k.created_at)}</td>
                <td className="row"><button className="btn btn-primary" onClick={() => review(k, "active")}>승인</button>
                  <button className="btn btn-pearl" onClick={() => review(k, "rejected")}>반려</button></td></tr>
            ))}
          </tbody></table>
        )}
      </section>
      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <section className="utility-card stack" aria-label="계정 목록">
          <h3 className="t-body-strong">계정 ({accs.length})</h3>
          <table><thead><tr><th>아이디</th><th>이름</th><th>역할</th><th>상태</th><th>키</th><th>마지막 로그인</th><th /></tr></thead><tbody>
            {accs.map((a) => (
              <tr key={a.account_id}><td>{a.login_id}</td><td>{a.name}</td>
                <td><select className="input" aria-label={`${a.login_id} 역할`} value={a.role} onChange={(e) => update(a, { role: e.target.value as Role }, `${a.login_id} 역할 → ${ROLE_LABEL[e.target.value as Role]} (세션 끊김)`)}>
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></td>
                <td>{STATUS[a.status]}{a.status === "pending" && <> <button className="btn btn-pearl" onClick={() => update(a, { status: "active" }, `${a.login_id} 사용 허용`)}>허용</button></>}</td><td className="num">{a.active_keys}</td><td>{fmtTime(a.last_login_at)}</td>
                <td>{a.status === "active" ? <button className="btn btn-pearl" onClick={() => update(a, { status: "disabled" }, `${a.login_id} 정지 — 세션·키 거부`)}>정지</button>
                  : a.status === "disabled" ? <button className="btn btn-pearl" onClick={() => update(a, { status: "active" }, `${a.login_id} 다시 사용`)}>해제</button> : null}
                  {" "}<button className="btn btn-pearl" onClick={() => showHist(a)} title="역할·상태 변경 이력 — 누가 언제 바꿨는지">이력</button></td></tr>
            ))}
          </tbody></table>
          {hist && <div className="stack" aria-label="변경 이력">
            <div className="row" style={{ justifyContent: "space-between" }}><b>{hist.acc.login_id} 변경 이력 ({hist.rows.length})</b><button className="btn btn-pearl" onClick={() => setHist(null)}>닫기</button></div>
            {hist.rows.length ? <table><thead><tr><th>시각</th><th>변경</th><th>누가</th></tr></thead><tbody>
              {hist.rows.map((c) => <tr key={c.change_id}><td>{fmtTime(c.changed_at)}</td><td>{changeText(c)}</td><td>{c.changed_by === "signup" ? "본인 가입" : c.changed_by}</td></tr>)}
            </tbody></table> : <span className="t-caption muted">기록 없음 — 이력 기능(2026-09-30) 이전의 변경은 남아 있지 않다</span>}
          </div>}
        </section>
        <form className="utility-card stack" onSubmit={create} aria-label="계정 만들기">
          <h3 className="t-body-strong">계정 만들기 (관제 담당자·운영 관리자 등 — 바로 사용)</h3>
          <label className="field"><span className="t-caption">아이디</span><input className="input" value={nc.login_id} onChange={(e) => setNc({ ...nc, login_id: e.target.value.toLowerCase() })} /></label>
          <label className="field"><span className="t-caption">이름</span><input className="input" value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} /></label>
          <label className="field"><span className="t-caption">소속 (선택)</span><input className="input" value={nc.org} onChange={(e) => setNc({ ...nc, org: e.target.value })} /></label>
          <label className="field"><span className="t-caption">초기 비밀번호 (8자 이상)</span><input className="input" type="password" autoComplete="new-password" value={nc.password} onChange={(e) => setNc({ ...nc, password: e.target.value })} /></label>
          <label className="field"><span className="t-caption">역할</span><select className="input" value={nc.role} onChange={(e) => setNc({ ...nc, role: e.target.value as Role })}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></label>
          <button className="btn btn-primary" disabled={!nc.login_id || !nc.name || nc.password.length < 8}>만들기</button>
        </form>
      </div>
      <section className="utility-card stack" style={{ marginTop: 16 }} aria-label="발급된 API 키">
        <h3 className="t-body-strong">API 키 전체 (사용 중 {keys.filter((k) => !k.revoked_at && k.status === "active").length}개) — 원문은 저장하지 않는다</h3>
        <table><thead><tr><th>계정</th><th>이름</th><th>앞자리</th><th>발급</th><th>마지막 사용</th><th>상태</th><th /></tr></thead><tbody>
          {keys.length === 0 && <tr><td colSpan={7} className="muted">발급된 키가 없다</td></tr>}
          {keys.map((k) => (
            <tr key={k.key_id}><td>{k.login_id}</td><td>{k.name}</td><td><code>{k.key_prefix}…</code></td><td>{fmtTime(k.created_at)}</td><td>{fmtTime(k.last_used_at)}</td>
              <td>{KEY_STATE(k)}</td>
              <td>{!k.revoked_at && <button className="btn btn-pearl" onClick={() => window.confirm(`${k.login_id} 의 «${k.name}» 키를 폐기한다`) && run(() => del(`/v1/admin/api-keys/${k.key_id}`, { admin: true }), `${k.key_prefix}… 폐기`)}>폐기</button>}</td></tr>
          ))}
        </tbody></table>
      </section>
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
    </>
  );
}
