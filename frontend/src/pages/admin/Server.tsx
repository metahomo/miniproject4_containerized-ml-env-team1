/* S1 서버 준비 — 검출기 적재 상태(로딩 시간), 재적재, 받은 요청(C7, 결정 D10).
   웹서비스 연동 등록·시험 호출·호스트 단계 표는 2026-09-30 삭제 — 웹과 API 가 한 프로세스(R21-D1)라 할 일이 없다. */
import { useCallback, useEffect, useState } from "react";
import { ApiError, fmtTime, get, post, type GateError } from "../../api/client";
import type { GateEvent } from "../../api/types";
import { GateBlock } from "../../components/GateBlock";
import { useReadiness } from "../../stores/readiness";
import { useCodes } from "../../stores/auth";

interface Detector { kind: string; model: string; loaded: boolean; load_seconds?: number | null; warmed_up_at?: string | null; last_infer_ms?: number | null; note?: string | null; available?: Record<string, unknown>; ollama?: Record<string, unknown> }

export default function Server() {
  const c = useCodes();   // 설계 번호는 화면에 보이지 않게 (2026-09-30)
  const { readiness, refresh } = useReadiness();
  const [det, setDet] = useState<Detector | null>(null);
  const [requests, setRequests] = useState<GateEvent[]>([]);
  const [gate, setGate] = useState<GateError | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => {
    get<Detector>("/v1/admin/detector", { admin: true }).then(setDet).catch(() => setDet(null));
    get<GateEvent[]>("/v1/admin/gate-events", { admin: true, query: { requested_only: "true" } }).then(setRequests).catch(() => setRequests([]));
  }, []);
  useEffect(load, [load, readiness?.updated_at]);

  const preload = async () => { setBusy("preload"); setGate(null); try { await post("/v1/admin/detector/preload", { admin: true }); await refresh(); load(); } catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : null); } finally { setBusy(null); } };
  const state = readiness?.readiness === "ready" ? "진단 가능" : readiness?.readiness === "preparing" ? "준비 중" : "진단 불가";
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">서버 준비</h1><p className="t-caption">검출기 적재·웜업 시간이 준비 상태를 결정한다{c(" (G0)")}</p></div>
      <section className="utility-card stack">
        <div className="row" style={{ justifyContent: "space-between" }}><h3 className="t-body-strong">검출기 상태</h3>
          <div className="row"><button className="btn btn-pearl" onClick={() => { refresh(); load(); }}>새로고침</button><button className="btn btn-dark-utility" onClick={preload} disabled={busy === "preload"} title="검출기 (재)적재·웜업. Ollama 검출기면 공유 서버에 미리 올린다 (가이드 1.6)">{busy === "preload" ? "적재 중…" : "검출기 재적재 · 웜업"}</button></div></div>
        <p>준비 상태: <b>{state}</b>{readiness ? <span className="t-caption muted"> · 갱신 {fmtTime(readiness.updated_at)}</span> : null}</p>
        <p className="t-caption">{det ? `${det.kind} · ${det.model} · 커밋 ${readiness?.model_commit ?? "—"} · ${det.loaded ? "적재 완료" : "적재 진행 중 / 실패"} · 적재 ${det.load_seconds ?? "?"}s · 웜업 ${fmtTime(det.warmed_up_at)} · 최근 추론 ${det.last_infer_ms ?? "?"}ms${det.note ? " · " + det.note : ""}` : "검출기 정보를 불러오지 못했다"}</p>
        {det?.ollama && <p className="t-caption muted">Ollama: {JSON.stringify(det.ollama)}</p>}
      </section>
      <section className="utility-card stack" style={{ marginTop: 16 }} aria-label="받은 요청">
        <h3 className="t-body-strong">받은 요청 ({requests.length})</h3>
        <p className="t-caption muted">이용자가 차단 블록의 «요청 보내기»로 보낸 해제 요청 중 아직 풀리지 않은 것. 해당 화면에서 원인을 해소하면 목록에서 빠진다</p>
        {requests.length ? <table><thead><tr><th>요청 시각</th><th>요청자</th><th>게이트</th><th>화면</th><th>대상</th><th>사유</th></tr></thead>
          <tbody>{requests.map((r) => <tr key={r.event_id}><td>{fmtTime(r.request_sent_at)}</td><td>{r.request_sent_by ?? "—"}</td><td><b>{r.gate_code}</b></td><td>{r.screen_code}</td><td>{r.subject_kind} {r.subject_id}</td><td>{r.reason_text ?? r.reason_code}</td></tr>)}</tbody></table>
          : <span className="t-caption muted">받은 요청이 없다</span>}
      </section>
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
    </>
  );
}
