/* 권한 매트릭스 (S10, RBAC — 운영 관리자) — 사용자 유형(역할)×기능 칸을 체크해 기능 활용 여부를 정한다.
   저장하면 서버가 바로 그 표로 호출을 거른다(칸이 꺼진 역할은 403 ROLE_FORBIDDEN). 바꾼 칸만 저장되고 나머지는 기본값(rbac.py).
   잠긴 칸: 운영 관리자 열(모두 허용)·계정/관리 행(운영 관리자만) — 관리 권한을 스스로 잃지 않게. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, fmtTime, get, put, type GateError } from "../../api/client";
import { GateBlock } from "../../components/GateBlock";
import { SHOW_DESIGN_CODES, refreshPerms } from "../../stores/auth";

/** 서버의 기능 이름에 붙은 UC 번호 "(UC1)" 는 화면에서 뗀다 (2026-09-30) */
const featLabel = (l: string) => (SHOW_DESIGN_CODES ? l : l.replace(/\s*\(UC[^)]*\)/g, ""));

interface RoleCol { role: string; label: string; locked: boolean }
interface PermRow { permission: string; label: string; roles: string[]; default_roles: string[]; locked_roles: string[] }
interface MatrixView { roles: RoleCol[]; permissions: PermRow[]; changed_cells: number; updated_at: string | null; updated_by: string | null }
type Grid = Record<string, Set<string>>;

const ROLE_HINT: Record<string, string> = {
  user: "회원가입하면 바로",
  integration: "승인된 API 키(cvk_)",
  webservice: "서버 설정 호출 키",
  controller: "운영 관리자가 부여",
  admin: "운영 관리자가 부여 · 관리자 키",
};

const toGrid = (rows: PermRow[]): Grid => Object.fromEntries(rows.map((p) => [p.permission, new Set(p.roles)]));
const same = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x));

export default function Rbac() {
  const [view, setView] = useState<MatrixView | null>(null);
  const [grid, setGrid] = useState<Grid>({});
  const [gate, setGate] = useState<GateError | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fail = (err: unknown) => setGate(err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" });
  const apply = (v: MatrixView) => { setView(v); setGrid(toGrid(v.permissions)); };
  const load = useCallback(() => { get<MatrixView>("/v1/admin/rbac", { admin: true }).then(apply).catch(fail); }, []);
  useEffect(() => { load(); }, [load]);

  const saved = useMemo(() => toGrid(view?.permissions ?? []), [view]);
  const dirty = useMemo(() => (view?.permissions ?? []).reduce((n, p) => n + (view!.roles.filter((r) =>
    (grid[p.permission]?.has(r.role) ?? false) !== saved[p.permission].has(r.role)).length), 0), [grid, saved, view]);

  if (!view) return gate ? <GateBlock error={gate} onRetry={() => { setGate(null); load(); }} /> : <p className="muted">권한 매트릭스를 불러오는 중…</p>;

  const isLocked = (p: PermRow, role: string) => p.locked_roles.includes(role);
  const toggle = (p: PermRow, role: string) => {
    if (isLocked(p, role)) return;
    setGrid((g) => {
      const s = new Set(g[p.permission]);
      if (s.has(role)) s.delete(role); else s.add(role);
      return { ...g, [p.permission]: s };
    });
  };
  // 열 머리 — 그 역할의 잠기지 않은 칸을 모두 켜기/끄기
  const toggleColumn = (role: string) => {
    const open = view.permissions.filter((p) => !isLocked(p, role));
    const allOn = open.every((p) => grid[p.permission].has(role));
    setGrid((g) => {
      const next = { ...g };
      open.forEach((p) => { const s = new Set(next[p.permission]); if (allOn) s.delete(role); else s.add(role); next[p.permission] = s; });
      return next;
    });
  };
  const toDefaults = () => setGrid(Object.fromEntries(view.permissions.map((p) => [p.permission, new Set(p.default_roles)])));
  const save = async () => {
    setBusy(true); setGate(null); setMsg(null);
    try {
      const body = { permissions: Object.fromEntries(view.permissions.map((p) => [p.permission, view.roles.map((r) => r.role).filter((r) => grid[p.permission].has(r))])) };
      const v = await put<MatrixView>("/v1/admin/rbac", { admin: true, body });
      apply(v);
      refreshPerms();   // 내 메뉴·화면 게이트도 바로 새 권한으로
      setMsg(`권한 매트릭스를 저장했다 — 바로 적용 (기본값과 다른 칸 ${v.changed_cells}개)`);
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  const isDefault = view.permissions.every((p) => same(grid[p.permission], new Set(p.default_roles)));

  return (
    <>
      <div className="page-title"><h1 className="t-display-md">권한 매트릭스</h1>
        <p className="t-caption">사용자 유형별로 쓸 수 있는 기능을 체크한다. 저장하면 서버가 바로 이 표로 요청을 거른다(꺼진 칸 → 403). 🔒 칸은 관리 권한을 잃지 않도록 잠겨 있다.</p></div>
      {msg && <div className="toast" role="status">{msg}</div>}
      <section className="utility-card stack" aria-label="역할별 기능 권한">
        <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
          <span className="t-caption muted">
            {view.updated_at ? `마지막 변경 ${fmtTime(view.updated_at)} · ${view.updated_by}` : "기본값 그대로"} · 기본값과 다른 칸 {view.changed_cells}개
          </span>
          <div className="row">
            <button className="btn btn-pearl" onClick={toDefaults} disabled={isDefault || busy}>기본값으로</button>
            <button className="btn btn-pearl" onClick={() => setGrid(toGrid(view.permissions))} disabled={!dirty || busy}>되돌리기</button>
            <button className="btn btn-primary" onClick={save} disabled={!dirty || busy}>{busy ? "저장 중…" : dirty ? `저장 (${dirty}칸 변경)` : "저장"}</button>
          </div>
        </div>
        <div className="rbac-wrap">
          <table className="rbac-matrix">
            <thead><tr>
              <th scope="col" className="feat">기능 ↓ · 사용자 유형 →</th>
              {view.roles.map((r) => (
                <th key={r.role} scope="col">
                  <button type="button" className="rbac-col" onClick={() => toggleColumn(r.role)} disabled={r.locked} title={r.locked ? "잠김 — 항상 모두 허용" : `${r.label} 열 전체 켜기/끄기`}>
                    <b>{r.label}{r.locked && " 🔒"}</b><span className="t-caption muted">{ROLE_HINT[r.role] ?? r.role}</span>
                  </button>
                </th>
              ))}
            </tr></thead>
            <tbody>
              {view.permissions.map((p) => (
                <tr key={p.permission}>
                  <th scope="row" className="feat">{featLabel(p.label)}<code className="t-caption muted">{p.permission}</code></th>
                  {view.roles.map((r) => {
                    const on = grid[p.permission]?.has(r.role) ?? false;
                    const lock = isLocked(p, r.role);
                    const changed = on !== saved[p.permission].has(r.role);
                    const custom = on !== p.default_roles.includes(r.role);
                    return (
                      <td key={r.role} className={"cell" + (changed ? " changed" : "") + (lock ? " locked" : "")}
                        title={lock ? "잠김" : custom ? "기본값과 다름" : "기본값"}>
                        <label>
                          <input type="checkbox" checked={on} disabled={lock} onChange={() => toggle(p, r.role)} aria-label={`${r.label} — ${featLabel(p.label)}`} />
                          {lock ? <span className="lock" aria-hidden>🔒</span> : custom ? <span className="dot" aria-hidden /> : null}
                        </label>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot><tr>
              <th scope="row" className="feat t-caption">허용 기능 수</th>
              {view.roles.map((r) => <td key={r.role} className="num">{view.permissions.filter((p) => grid[p.permission]?.has(r.role)).length} / {view.permissions.length}</td>)}
            </tr></tfoot>
          </table>
        </div>
        <p className="t-caption muted">
          <span className="rbac-legend changed" /> 저장 전 바꾼 칸 · <span className="dot" /> 기본값과 다른 칸 · 🔒 잠긴 칸.
          화면 메뉴는 역할 기준 그대로이고, 매트릭스는 서버가 API 요청을 거르는 기준이다.
        </p>
      </section>
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
    </>
  );
}
