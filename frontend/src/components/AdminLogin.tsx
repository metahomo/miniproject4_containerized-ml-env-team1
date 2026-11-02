/* 로그인·역할 게이트 (RBAC T107·T108 · G1). 역할은 유스케이스 액터 — 일반 사용자·관제 담당자·운영 관리자.
   - 로그인 화면(pages/Login)과 헤더가 같은 폼을 쓴다. 헤더는 로그인 후 «이름 · 역할 · 로그아웃»
   - 역할 화면: 역할이 맞지 않으면 G1 차단 블록 + 로그인 폼 (UC6 E3·UC7 E2·UC8 E2·UC11 E2·UC12 E4 — 권한 없는 주체의 변경 시도는 거부)
   - 관리자 키 로그인(T095)은 계정을 만들기 전 최초 운영 관리자용으로 남긴다. */
import { useState } from "react";
import { Link } from "react-router-dom";
import { PERM_LABEL, ROLE_LABEL, login, loginPassword, logout, useAuth, useCodes, usePerms, type Perm, type Role } from "../stores/auth";

export function LoginForm({ onDone, autoFocus }: { onDone?: () => void; autoFocus?: boolean }) {
  const [mode, setMode] = useState<"password" | "key">("password");
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    const r = mode === "password" ? await loginPassword(id, pw) : await login(key);
    setBusy(false);
    if (r.ok) { setPw(""); setKey(""); onDone?.(); } else setErr(r.reason ?? "로그인 실패");
  };
  const inp = { minHeight: 36, width: "100%", maxWidth: 360, padding: "6px 12px" };
  return (
    <form className="stack" onSubmit={submit} aria-label="로그인" style={{ gap: 8 }}>
      {mode === "password" ? (
        <>
          <input className="input" autoComplete="username" autoFocus={autoFocus} placeholder="아이디" aria-label="아이디" value={id} onChange={(e) => setId(e.target.value)} style={inp} />
          <input className="input" type="password" autoComplete="current-password" placeholder="비밀번호" aria-label="비밀번호" value={pw} onChange={(e) => setPw(e.target.value)} style={inp} />
        </>
      ) : (
        <input className="input" type="password" autoComplete="off" autoFocus={autoFocus} placeholder="관리자 키" aria-label="관리자 키" value={key} onChange={(e) => setKey(e.target.value)} style={inp} />
      )}
      <button className="btn btn-primary" style={{ width: "100%", maxWidth: 360 }} type="submit" disabled={busy || (mode === "password" ? !id.trim() || !pw : !key.trim())}>{busy ? "확인 중…" : "로그인"}</button>
      {err && <span className="t-caption" role="alert" style={{ color: "var(--status-crowded)" }}>{err}</span>}
      <p className="t-caption muted row" style={{ justifyContent: "space-between" }}>
        <span>계정이 없으면 <Link to="/signup" onClick={onDone}><b>회원가입</b></Link></span>
        {/* 관리자 키는 계정을 만들기 전 최초 설정용 (T095) — 눈에 띄지 않게 */}
        <button type="button" className="linklike t-caption muted" style={{ background: "none", border: 0, padding: 0, cursor: "pointer" }} onClick={() => { setMode(mode === "password" ? "key" : "password"); setErr(null); }}>
          {mode === "password" ? "관리자 키" : "아이디로 로그인"}
        </button>
      </p>
    </form>
  );
}

/** 헤더 — 로그인 전 «로그인», 로그인 후 «이름 · 역할 · 로그아웃» */
export function AdminLoginChip() {
  const me = useAuth();
  const [open, setOpen] = useState(false);
  if (me) {
    return (
      <span className="chip" title={`${me.login_id} — 이 브라우저에만 로그인돼 있다`}>
        {me.name} · <b>{ROLE_LABEL[me.role]}</b>
        <button className="btn btn-pearl" style={{ minHeight: 28, padding: "2px 10px" }} onClick={logout}>로그아웃</button>
      </span>
    );
  }
  return (
    <span style={{ position: "relative" }}>
      <button className="btn btn-pearl" style={{ minHeight: 32 }} onClick={() => setOpen((o) => !o)} aria-expanded={open}>로그인</button>
      {open && (
        <div style={{ position: "absolute", right: 0, top: "calc(100% + 6px)", zIndex: 20, background: "var(--color-canvas)", border: "var(--border-hairline)",
          borderRadius: 10, padding: 12, boxShadow: "var(--shadow-product)", minWidth: 320 }}>
          <LoginForm autoFocus onDone={() => setOpen(false)} />
        </div>
      )}
    </span>
  );
}

/** 권한 화면 — 유효 권한(권한 매트릭스 S10, T110)이 없으면 G1 차단 블록 + 로그인 폼 */
export function PermGate({ perm, children, why }: { perm: Perm; children: React.ReactNode; why?: string }) {
  const me = useAuth();
  const perms = usePerms();
  const c = useCodes();
  if (me && perms.includes(perm)) return <>{children}</>;
  return (
    <section className="gate" style={{ maxWidth: 640 }} aria-label="로그인 필요">
      <p className="t-body-strong">차단 상태{c(" · G1")} — «{PERM_LABEL[perm]}» 권한이 있어야 이용할 수 있는 화면이다</p>
      <p className="t-caption">
        {why ?? "권한이 있는 계정으로 로그인하면 열린다."}
        {me && ` 지금 로그인: ${me.name} (${ROLE_LABEL[me.role]}).`} 해제 주체: 운영 관리자(역할 부여 · 권한 매트릭스)
      </p>
      <div style={{ marginTop: 12 }}><LoginForm autoFocus /></div>
      <p className="t-caption muted" style={{ marginTop: 8 }}>역할별로 쓸 수 있는 기능은 운영 관리자가 권한 매트릭스에서 정한다. 다른 계정으로 로그인하려면 위 폼을 쓴다</p>
    </section>
  );
}

/** 역할 화면 (T107) — 지금 화면은 PermGate 를 쓴다. 역할 자체를 봐야 할 때만 */
export function RoleGate({ roles, children, why }: { roles: Role[]; children: React.ReactNode; why?: string }) {
  const me = useAuth();
  const c = useCodes();
  if (me && roles.includes(me.role)) return <>{children}</>;
  const who = roles.map((r) => ROLE_LABEL[r]).join("·");
  return (
    <section className="gate" style={{ maxWidth: 640 }} aria-label="로그인 필요">
      <p className="t-body-strong">차단 상태{c(" · G1")} — {who} 만 이용할 수 있는 화면이다</p>
      <p className="t-caption">
        {why ?? "권한이 있는 계정으로 로그인하면 열린다."}
        {me && ` 지금 로그인: ${me.name} (${ROLE_LABEL[me.role]}).`} 해제 주체: 운영 관리자(역할 부여)
      </p>
      <div style={{ marginTop: 12 }}><LoginForm autoFocus /></div>
      <p className="t-caption muted" style={{ marginTop: 8 }}>기본 기능(버스 조회·API 키)은 어느 역할로든 로그인하면 쓸 수 있다. 다른 계정으로 로그인하려면 위 폼을 쓴다</p>
    </section>
  );
}

/** 운영 관리자 화면 */
export function AdminGate({ children }: { children: React.ReactNode }) {
  return <PermGate perm="admin" why="카메라·ROI·정원·등급 기준·차량 매핑·시연 모드는 운영 관리자만 바꾼다.">{children}</PermGate>;
}
