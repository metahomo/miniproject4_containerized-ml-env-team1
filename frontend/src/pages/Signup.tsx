/* 회원가입 (RBAC T107·T108) — 가입하면 바로 일반 사용자로 로그인한다. API 키는 로그인 후 «API 키»에서 신청 → 운영 관리자 승인.
   관제 담당자·운영 관리자 역할은 운영 관리자가 «계정·키 관리»에서 준다. */
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, post, type GateError } from "../api/client";
import { loginPassword } from "../stores/auth";
import { GateBlock } from "../components/GateBlock";

const LOGIN_RE = /^[a-z0-9][a-z0-9._-]{2,39}$/;

export default function Signup() {
  const [f, setF] = useState({ login_id: "", name: "", org: "", email: "", password: "", password2: "" });
  const [gate, setGate] = useState<GateError | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const chk = { id: LOGIN_RE.test(f.login_id), pw: f.password.length >= 8, same: f.password === f.password2, name: f.name.trim().length > 0 };
  const ok = chk.id && chk.pw && chk.same && chk.name;
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); if (!ok) return;
    setBusy(true); setGate(null);
    try {
      const r = await post<{ message: string }>("/v1/auth/signup", { body: { login_id: f.login_id, name: f.name.trim(), password: f.password, org: f.org.trim() || null, email: f.email.trim() || null } });
      setDone(r.message);
      await loginPassword(f.login_id, f.password);   // 가입 = 바로 로그인 (T108)
    } catch (err) {
      setGate(err instanceof ApiError && err.gate ? err.gate : { gate: "G2", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" });
    } finally { setBusy(false); }
  };
  const bad = (t: string) => <span className="t-caption" style={{ color: "var(--status-crowded)" }}>{t}</span>;
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">회원가입</h1>
        <p className="t-caption">가입하면 바로 로그인된다</p></div>
      {done ? (
        <section className="utility-card stack" style={{ maxWidth: 560 }} role="status">
          <h3 className="t-body-strong">가입 완료 — 일반 사용자</h3>
          <p>{done}</p>
          <div className="row"><Link className="btn btn-primary" to="/">로그인 화면으로</Link></div>
        </section>
      ) : (
        <form className="utility-card stack" style={{ maxWidth: 560 }} onSubmit={submit} aria-label="회원가입">
          <label className="field"><span className="t-caption">아이디 (영문 소문자·숫자·._- 3~40자)</span><input className="input" autoComplete="username" value={f.login_id} onChange={(e) => setF({ ...f, login_id: e.target.value.toLowerCase() })} />{f.login_id && !chk.id && bad("형식이 맞지 않는다")}</label>
          <label className="field"><span className="t-caption">이름</span><input className="input" value={f.name} onChange={set("name")} /></label>
          <label className="field"><span className="t-caption">소속 (선택)</span><input className="input" value={f.org} onChange={set("org")} /></label>
          <label className="field"><span className="t-caption">이메일 (선택 — 승인 연락용)</span><input className="input" type="email" value={f.email} onChange={set("email")} /></label>
          <label className="field"><span className="t-caption">비밀번호 (8자 이상)</span><input className="input" type="password" autoComplete="new-password" value={f.password} onChange={set("password")} />{f.password && !chk.pw && bad("8자 이상")}</label>
          <label className="field"><span className="t-caption">비밀번호 확인</span><input className="input" type="password" autoComplete="new-password" value={f.password2} onChange={set("password2")} />{f.password2 && !chk.same && bad("비밀번호가 다르다")}</label>
          <button className="btn btn-primary" disabled={!ok || busy}>{busy ? "가입 중…" : "가입"}</button>
          <p className="t-caption muted">계정이 있으면 <Link to="/">로그인</Link></p>
        </form>
      )}
      {gate && <div style={{ marginTop: 16, maxWidth: 560 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
    </>
  );
}
