/* S4 정확도 검증 — 일괄 제출(순서 유지) → 프레임별 결과 → 사람이 센 인원 입력 → SC-01·02 판정 → S3·S1 환류.
   정답은 사람이 센 인원만 받는다(2026-09-30) — 잔여 %·등급은 서버가 그 프레임의 정원·등급 기준으로 만든다(R22). */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, get, post, type GateError } from "../../api/client";
import type { BatchResult, VerificationRun } from "../../api/types";
import { GateBlock } from "../../components/GateBlock";
import { StatusBadge } from "../../components/StatusBadge";
import { WarningChips } from "../../components/WarningChips";
import { useCodes } from "../../stores/auth";

export default function Verification() {
  const c = useCodes();   // 설계 번호는 화면에 보이지 않게 (2026-09-30)
  const [cameraId, setCameraId] = useState("CAM-DEMO-01");
  const [files, setFiles] = useState<File[]>([]);
  const [batch, setBatch] = useState<BatchResult | null>(null);
  const [manual, setManual] = useState<Record<number, string>>({});   // 순서 → 사람이 센 인원
  const [csvNote, setCsvNote] = useState<string | null>(null);
  const [thr, setThr] = useState<{ free: number; crowded: number } | null>(null);   // 미리보기용 현재 등급 기준
  useEffect(() => { get<{ free_min_ratio: number; crowded_max_ratio: number }>("/v1/reference/threshold").then((t) => setThr({ free: t.free_min_ratio, crowded: t.crowded_max_ratio })).catch(() => setThr(null)); }, []);
  const [run, setRun] = useState<VerificationRun | null>(null);
  const [gate, setGate] = useState<GateError | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setGate(null); setBatch(null); setRun(null);
    const fd = new FormData(); fd.append("camera_id", cameraId); files.forEach((f) => fd.append("frames", f));
    try { setBatch(await post<BatchResult>("/v1/diagnose/batch", { admin: true, form: fd })); }
    catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : { gate: "—", reason_code: "ERROR", reason: (e as Error).message, resolver_role: "self" }); }
    finally { setBusy(false); }
  };
  const judge = async () => {
    if (!batch) return; setGate(null);
    const items = batch.items.map((it) => ({ seq: it.seq, manual_persons: manual[it.seq]?.trim() ? Number(manual[it.seq]) : null }));
    try { setRun(await post<VerificationRun>("/v1/admin/verification-runs", { admin: true, body: { batch_id: batch.batch_id, items } })); }
    catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : null); }
  };
  /** CSV: 첫 줄 제목 `seq,persons` — 순서, 사람이 센 인원 */
  const importCsv = (f: File) => f.text().then((t) => {
    const lines = t.split(/\r?\n/).filter((l) => l.trim());
    if (/manual_ratio|manual_level/.test(lines[0] ?? "")) { setCsvNote("이전 형식(잔여 %·등급)이다. 이제는 사람이 센 인원만 넣는다 — 제목 줄 seq,persons"); return; }
    const m: typeof manual = {};
    lines.slice(1).forEach((l) => { const [seq, n] = l.split(","); if (seq?.trim()) m[Number(seq)] = (n ?? "").trim(); });
    setManual(m); setCsvNote(`${Object.keys(m).length}줄을 불러왔다`);
  });
  /** 사람이 센 인원 → 잔여 % (R22, 0 에서 멈춤)·등급 미리보기. 판정은 서버가 그 프레임의 판본으로 다시 계산한다 */
  const preview = (n: string, capacity?: number | null) => {
    if (!n.trim() || !capacity || Number.isNaN(Number(n))) return null;
    const ratio = Math.max(0, 100 - (Number(n) / capacity) * 100);
    const level = thr ? (ratio >= thr.free ? "free" : ratio <= thr.crowded ? "crowded" : "normal") : null;
    return { ratio, level } as const;
  };
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">정확도 검증 — 사전 녹화 일괄</h1><p className="t-caption">N장(≤20)을 제출 순서대로 진단하고 사람이 직접 센 인원과 비교해 {c("SC-01")}(잔여 비율 ±10%p 안 85% 이상)·{c("SC-02")}(등급 일치 85% 이상)를 판정한다. 사람이 센 인원은 정원·등급 기준으로 잔여 %·등급으로 바뀐다. CSV: <code>seq,persons</code> (순서, 사람이 센 인원)</p></div>
      <section className="utility-card row" aria-label="4.1 일괄 제출">
        <label className="field" style={{ width: 200 }}><span className="t-caption">카메라</span><input className="input" value={cameraId} onChange={(e) => setCameraId(e.target.value)} /></label>
        <label className="field" style={{ minWidth: 280 }}><span className="t-caption">프레임 (순서 유지, ≤20장)</span><input className="input" type="file" multiple accept="image/jpeg,image/png" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} /></label>
        <label className="field" style={{ minWidth: 240 }}><span className="t-caption">사람이 센 인원 CSV (파일은 서버에 올라가지 않는다)</span><input className="input" type="file" accept=".csv" onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])} /></label>
        <button className="btn btn-primary" onClick={submit} disabled={busy || !files.length || files.length > 20} title={files.length > 20 ? `20장 한도${c(" (G2)")}` : ""}>{busy ? "검증 중…" : `검증 실행 (${files.length}장)`}</button>
      </section>
      {csvNote && <p className="t-caption muted" role="status" style={{ marginTop: 8 }}>{csvNote}</p>}
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
      {batch && (
        <section className="utility-card stack" style={{ marginTop: 16 }} aria-label="4.4 프레임별 결과">
          <h3 className="t-body-strong">4.4~4.5 프레임별 결과 (제출 순서, 단건과 동일)</h3>
          <table><thead><tr><th>순서</th><th>AI 인원</th><th>잔여 %</th><th>등급</th><th>경고</th><th>신뢰도</th><th>사람이 센 인원</th><th>→ 잔여 % · 등급</th><th>인원 차이</th><th>잔여 차이</th></tr></thead>
            <tbody>{batch.items.map((it) => { const a = it.assessment; const n = manual[it.seq] ?? ""; const pv = a ? preview(n, a.capacity) : null;
              const diff = a && pv ? (a.vacant_capacity_ratio - pv.ratio).toFixed(1) : "—";
              const pdiff = a && n.trim() && !Number.isNaN(Number(n)) ? a.person_count - Number(n) : null; return (
              <tr key={it.seq}><td>{it.seq}</td>
                <td className="num">{a ? `${a.person_count}${a.capacity ? ` / ${a.capacity}` : ""}` : "—"}</td>
                <td className="num">{a ? (a.is_reference_only ? `참고 ${a.vacant_capacity_ratio.toFixed(0)}` : a.vacant_capacity_ratio.toFixed(0)) : "—"}</td>
                <td>{a ? <StatusBadge level={a.crowding_level} /> : <b>반려</b>}</td>
                <td>{a ? <WarningChips warnings={a.warnings} /> : <span className="t-caption">{it.reject?.gate} {it.reject?.reason}</span>}</td>
                <td className="num">{a?.mean_confidence.toFixed(2) ?? "—"}</td>
                <td><input className="input" style={{ width: 90, minHeight: 36 }} inputMode="numeric" aria-label={`${it.seq}번 사람이 센 인원`} value={n} onChange={(e) => setManual({ ...manual, [it.seq]: e.target.value })} /></td>
                <td>{pv ? <span className="row" style={{ gap: 6 }}><span className="num">{pv.ratio.toFixed(0)}%</span>{pv.level && <StatusBadge level={pv.level} />}</span> : a && !a.capacity && n.trim() ? <span className="t-caption muted">정원 없음 — 판정 제외</span> : "—"}</td>
                <td className="num">{pdiff == null ? "—" : pdiff === 0 ? "0" : pdiff > 0 ? `+${pdiff}` : `${pdiff}`}</td>
                <td className="num">{a && a.crowding_level !== "uncertain" ? diff : <span className="muted">제외</span>}</td></tr>); })}</tbody></table>
          <p className="t-caption muted">인원 차이 = AI 인원 − 사람이 센 인원 (+ 면 AI 가 더 셈, − 면 놓침). 판독 불확실·반려 프레임은 판정에서 빠진다.</p>
          <p className="t-caption muted">정합성: ROI #{batch.consistency.roi_id} · 정원 #{batch.consistency.spec_id ?? "없음"} · 등급 기준 #{batch.consistency.threshold_policy_id} 동일 적용{c(" (BR-CV-12)")} · 원본 {batch.consistency.frames_discarded}장 폐기 · 집계 기록 {batch.consistency.audit_records}건</p>
          <button className="btn btn-primary" onClick={judge}>4.7 정확도 판정</button>
        </section>
      )}
      {run && (
        <section className="utility-card stack" style={{ marginTop: 16 }} aria-label="4.7 판정">
          <div className="row" style={{ gap: 24 }}>
            <div><span className="t-caption muted">잔여 비율 ±10%p 일치율</span><br /><b className="t-display-md">{run.ratio_match_rate}%</b> <span className={"status " + (run.ratio_match_rate >= 85 ? "status-free" : "status-crowded")}>{run.ratio_match_rate >= 85 ? `${c("SC-01 ")}통과` : `${c("SC-01 ")}미달`}</span></div>
            <div><span className="t-caption muted">등급 일치율</span><br /><b className="t-display-md">{run.level_match_rate}%</b> <span className={"status " + (run.level_match_rate >= 85 ? "status-free" : "status-crowded")}>{run.level_match_rate >= 85 ? `${c("SC-02 ")}통과` : `${c("SC-02 ")}미달`}</span></div>
            <div><span className="t-caption muted">판정</span><br /><b className="t-display-md">{run.verdict === "pass" ? "통과" : "미달"}</b></div>
            {(() => { const ds = run.items.map((x) => x.persons_diff).filter((d): d is number => typeof d === "number");
              if (!ds.length) return null;
              const mean = ds.reduce((p, d) => p + d, 0) / ds.length, mae = ds.reduce((p, d) => p + Math.abs(d), 0) / ds.length;
              return <div><span className="t-caption muted">인원 차이 ({ds.length}장)</span><br /><b className="t-display-md">평균 {mae.toFixed(1)}명</b> <span className="t-caption muted">{mean < 0 ? `AI 가 평균 ${(-mean).toFixed(1)}명 적게 셈` : mean > 0 ? `AI 가 평균 ${mean.toFixed(1)}명 많이 셈` : "치우침 없음"}</span></div>; })()}
          </div>
          <p className="t-caption muted">적용 판본: 등급 기준 #{String(run.versions.threshold_policy_id)} · ROI #{String(run.versions.roi_id)} · 모델 <code>{String(run.versions.model_commit)}</code> — 판본이 바뀌면 이 판정은 자동 무효 처리된다{c(" (H8)")}</p>
          <div className="row"><Link className="btn btn-secondary" to="/admin/policy">정책 재조정{c(" S3")}</Link><Link className="btn btn-secondary" to="/admin/server">모델 갱신{c(" S1")}</Link><span className="chip">검증 결과 #{run.run_id} 저장됨</span></div>
        </section>
      )}
    </>
  );
}
