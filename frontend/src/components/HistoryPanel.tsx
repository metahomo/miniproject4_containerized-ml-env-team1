/* C9 이력 패널 — 판본 행을 시간 역순으로, 읽기 전용 */
import { fmtTime } from "../api/client";

export function HistoryPanel<T extends Record<string, unknown>>({ rows, columns, title }: { rows: T[]; columns: Array<{ key: keyof T & string; label: string; fmt?: (v: unknown) => string }>; title?: string }) {
  return (
    <section className="utility-card stack">
      {title && <h3 className="t-body-strong">{title}</h3>}
      {rows.length === 0 ? <p className="muted t-caption">이력 없음</p> : (
        <table>
          <thead><tr>{columns.map((c) => <th key={c.key} scope="col">{c.label}</th>)}<th scope="col">상태</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => <td key={c.key}>{c.fmt ? c.fmt(r[c.key]) : String(r[c.key] ?? "—")}</td>)}
                <td>{r["superseded_at"] || r["released_at"] ? <span className="muted">과거 ({fmtTime(String(r["superseded_at"] ?? r["released_at"]))})</span> : <b>현재</b>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
