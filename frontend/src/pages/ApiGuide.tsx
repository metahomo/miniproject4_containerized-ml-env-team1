/* S9 API 문서 — 가이드라인 / 매뉴얼 / 모델 카드. 준비 중이어도 열람 가능.
   2026-09-30: 운영 관리 메뉴로 옮김 — 이용자는 «API 키» 화면의 짧은 사용법만 본다.
   2026-09-30 삭제: 카탈로그 탭(Swagger /docs 와 겹침), 시험 호출(S5 사진 진단과 같은 기능이면서 더 약함). */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE, get } from "../api/client";
import type { ApiGuide as Guide } from "../api/types";
import { useCodes } from "../stores/auth";

type Tab = "guideline" | "manual" | "model";

function Md({ text }: { text: string }) {
  // 최소 마크다운: 제목·표·목록·코드블록·굵게 (외부 라이브러리 없이)
  const lines = text.split("\n"); const out: React.ReactNode[] = []; let i = 0;
  const inline = (s: string) => s.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((p, k) => p.startsWith("`") ? <code key={k}>{p.slice(1, -1)}</code> : p.startsWith("**") ? <b key={k}>{p.slice(2, -2)}</b> : p);
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("```")) { const buf: string[] = []; i++; while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]); i++; out.push(<pre key={i}>{buf.join("\n")}</pre>); continue; }
    if (l.startsWith("|")) { const rows: string[][] = []; while (i < lines.length && lines[i].startsWith("|")) { const cells = lines[i].split("|").slice(1, -1).map((c) => c.trim()); if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells); i++; }
      out.push(<table key={i}><thead><tr>{rows[0].map((c, k) => <th key={k}>{inline(c)}</th>)}</tr></thead><tbody>{rows.slice(1).map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table>); continue; }
    if (/^#{1,3} /.test(l)) { const lvl = l.indexOf(" "); const T = (lvl === 1 ? "h2" : "h3") as "h2" | "h3"; out.push(<T key={i} className={lvl === 1 ? "t-tagline" : "t-body-strong"} style={{ marginTop: 12 }}>{l.slice(lvl + 1)}</T>); i++; continue; }
    if (/^\d+\. |^- /.test(l)) { const items: string[] = []; while (i < lines.length && /^\d+\. |^- /.test(lines[i])) items.push(lines[i++].replace(/^\d+\. |^- /, "")); out.push(<ul key={i}>{items.map((t, k) => <li key={k}>{inline(t)}</li>)}</ul>); continue; }
    if (l.trim()) out.push(<p key={i}>{inline(l)}</p>);
    i++;
  }
  return <div className="stack" style={{ gap: 8 }}>{out}</div>;
}

export default function ApiGuide() {
  const c = useCodes();   // 설계 번호는 운영 관리자에게만
  const [g, setG] = useState<Guide | null>(null);
  const [tab, setTab] = useState<Tab>("guideline");
  useEffect(() => { get<Guide>("/v1/api-guide").then(setG).catch(() => setG(null)); }, []);
  const steps = (["guideline", "manual", "model"] as Tab[]).map((k, i) => ({ key: k, label: ["가이드라인", "매뉴얼", "모델 카드"][i], state: (tab === k ? "current" : "todo") as "current" | "todo" }));
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">API 문서</h1><p className="t-caption">{g ? `${g.version} · 갱신 ${g.updated_at.slice(0, 10)} · ` : ""}가이드라인·매뉴얼·모델 카드. 엔드포인트 목록·입출력은 자동 문서에 있다. 이 내용은 실제 계약과 대조 후 배포된다{c(" (G17)")}. <a href={(API_BASE || "") + "/docs"} target="_blank" rel="noreferrer">자동 문서(/docs) 열기</a></p></div>
      <div className="toast" role="note" style={{ marginBottom: 16 }}>API 키 받기: <Link to="/my/keys">API 키</Link>에서 연계 시스템별로 신청 → 운영 관리자 승인 → 요청 헤더 <code>X-API-Key</code> (승인 전 403 KEY_PENDING)</div>
      <div className="row" role="tablist" style={{ marginBottom: 16 }}>
        {steps.map((s) => <button key={s.key} role="tab" aria-selected={tab === s.key} className={"chip" + (tab === s.key ? " selected" : "")} onClick={() => setTab(s.key as Tab)}>{s.label}</button>)}
      </div>
      {!g && <section className="utility-card"><p className="muted">안내를 불러오는 중이거나 서버에 연결할 수 없다.</p></section>}
      {g && tab === "guideline" && <section className="utility-card"><Md text={g.guideline_md} /></section>}
      {g && tab === "manual" && <section className="utility-card"><Md text={g.manual_md} /></section>}
      {g && tab === "model" && <section className="utility-card"><Md text={g.model_card_md} /></section>}
    </>
  );
}
