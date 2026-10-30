/* 일반 사용자 상단 바 (2026-09-30 홈 단순화) — 사이드바 대신. 서비스 이름(=버스 조회) · API 키 · 로그아웃만. */
import { NavLink } from "react-router-dom";
import { logout, useAuth, usePerms } from "../stores/auth";

export function SimpleBar() {
  const me = useAuth();
  const perms = usePerms();
  return (
    <header className="simple-bar">
      <NavLink to="/" end className="brand-link">대전 버스 혼잡도</NavLink>
      <nav className="row" aria-label="주 메뉴">
        {perms.includes("own_keys") && <NavLink to="/my/keys" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>API 키</NavLink>}
        <span className="t-caption muted" title={me?.login_id}>{me?.name}</span>
        <button className="btn btn-pearl" style={{ minHeight: 30, padding: "2px 12px" }} onClick={logout}>로그아웃</button>
      </nav>
    </header>
  );
}
