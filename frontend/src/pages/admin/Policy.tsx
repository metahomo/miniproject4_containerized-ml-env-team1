/* S3 진단 정책 설정 — 등급 기준(UC8)·인원 세기 기준(R22) 행별 검증, 유효 시간 규칙의 노선별 예외(UC11), 노선별 미리보기(출처 열), 이력, 검증 환류.
   2026-09-30 삭제: 시연 모드 스위치(S8 8.2·8.5 와 겹치고 S8 의 순서 강제를 우회), 계수·상한·자료 없음 기본·합산 시각 창 입력(바꿔 쓰지 않음 — 저장 때 현재 값을 그대로 보낸다). */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, fmtTime, get, post, type GateError, kst, kstDate, kstInputToUtc, kstNowInput } from "../../api/client";
import type { ThresholdPolicy, ValidityPolicyView } from "../../api/types";
import { GateBlock } from "../../components/GateBlock";
import { HistoryPanel } from "../../components/HistoryPanel";
import { refreshDemo } from "../../stores/demo";
import { designCode, useCodes } from "../../stores/auth";

// 입력칸은 한국 시각. 기본값은 "1분 뒤" — 전에는 "내일 이 시각"이라 날짜를 안 고치고 저장하면 하루 뒤로 예약됐다(2026-09-30 판본 2·3 사고)
const soon = () => kstNowInput(60000);

/** 저장 후 안내 — 몇 분 이상 뒤면 "예약"임을 분명히 알린다 (바로 적용된 줄 알고 다시 저장하는 일을 막는다) */
const thrSavedMsg = (utc: string) => {
  const mins = Math.round((Date.parse(utc + "Z") - Date.now()) / 60000);
  return mins > 2
    ? `예약됨 — ${kst(utc).slice(0, 16).replace("T", " ")} (한국 시각)부터 적용. 그 전까지는 현재 판본이 쓰인다. 등급 일치율${designCode("(SC-02)")} 재검증 필요`
    : `등급 기준 저장 — 1분 안에 적용된다. 등급 일치율${designCode("(SC-02)")} 재검증 필요`;
};

/** 노선 이름 «102번 · 간선 · 수통골기점지↔대전역 (30300037)» → 표시 이름(끝의 노선 ID 뺌)·버스 번호(«102») */
const busNo = (r: { route_id: string; route_name?: string | null }) => (r.route_name ?? r.route_id).replace(/\s*\([^)]*\)\s*$/, "");
const busNum = (r: { route_id: string; route_name?: string | null }) => (busNo(r).match(/^(\S+?)번/)?.[1] ?? busNo(r));

export default function Policy() {
  const c = useCodes();   // 설계 번호는 화면에 보이지 않게 (2026-09-30)
  const [thr, setThr] = useState<ThresholdPolicy[]>([]);
  const [val, setVal] = useState<ValidityPolicyView | null>(null);
  const [t, setT] = useState({ free_min_ratio: "50", crowded_max_ratio: "20", count_conf_min: "", effective_from: soon() });
  const [effConf, setEffConf] = useState<number | null>(null);   // 지금 실제로 쓰는 인원 세기 기준 (판본 값 또는 설정 기본값)
  const [exceptions, setExceptions] = useState("");
  const [excErr, setExcErr] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);   // 노선별 미리보기 — 처음엔 5개만
  const [gate, setGate] = useState<GateError | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const rows = await get<ThresholdPolicy[]>("/v1/admin/policies/threshold", { admin: true }); setThr(rows);
      const ref = await get<{ free_min_ratio: number; crowded_max_ratio: number; count_conf_min_effective: number }>("/v1/reference/threshold").catch(() => null);
      if (ref) {
        setEffConf(ref.count_conf_min_effective);
        // 새 값 입력칸은 지금 적용 중인 값으로 채운다 (비어 있을 때만 — 입력 중인 값은 덮지 않음)
        setT((s) => ({ ...s, free_min_ratio: s.free_min_ratio || String(ref.free_min_ratio), crowded_max_ratio: s.crowded_max_ratio || String(ref.crowded_max_ratio),
          count_conf_min: s.count_conf_min || String(ref.count_conf_min_effective) }));
      }
      const vv = await get<ValidityPolicyView>("/v1/admin/policies/validity", { admin: true }); setVal(vv);
      // 버스 번호로 보이되, 같은 번호의 노선이 여럿이면 노선 ID 로 (저장 때 다시 찾을 수 있게)
      const count = new Map<string, number>(); vv.preview.forEach((p) => count.set(busNum(p), (count.get(busNum(p)) ?? 0) + 1));
      const label = (id: string) => { const p = vv.preview.find((x) => x.route_id === id); return p && count.get(busNum(p)) === 1 ? `${busNum(p)}번` : id; };
      setExceptions((vv.policy.route_exceptions ?? []).map((e) => `${label(e.route_id)}:${e.minutes}`).join(", "));
    } catch (e) { if (e instanceof ApiError && e.gate) setGate(e.gate); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const run = async (fn: () => Promise<unknown>, ok: string) => { setGate(null); setMsg(null); try { await fn(); setMsg(ok); await load(); await refreshDemo(); } catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : { gate: "—", reason_code: "ERROR", reason: (e as Error).message, resolver_role: "self" }); } };
  const cur = thr.find((x) => x.is_current);
  const sched = thr.filter((x) => x.is_scheduled);
  const conf = Number(t.count_conf_min);
  const chk = { conf: conf >= 0.05 && conf <= 0.95, range: Number(t.free_min_ratio) >= 0 && Number(t.free_min_ratio) <= 100 && Number(t.crowded_max_ratio) >= 0 && Number(t.crowded_max_ratio) <= 100, order: Number(t.crowded_max_ratio) < Number(t.free_min_ratio), future: kstInputToUtc(t.effective_from) > new Date().toISOString().slice(0, 19) };
  const thrOk = chk.conf && chk.range && chk.order && chk.future;
  const saveThr = () => run(() => post("/v1/admin/policies/threshold", { admin: true, body: { free_min_ratio: Number(t.free_min_ratio), crowded_max_ratio: Number(t.crowded_max_ratio), count_conf_min: conf, effective_from: kstInputToUtc(t.effective_from) } }), thrSavedMsg(kstInputToUtc(t.effective_from)));
  // 노선별 예외만 바꾼다. 나머지 값과 시연 모드(S8 에서 켜고 끔)는 저장 직전의 현재 판본 그대로 — 화면을 연 뒤 S8 에서 바뀌었어도 덮지 않는다
  /** «102번:12, 311:8» → 노선 ID. 버스 번호(«번» 생략 가능) 또는 노선 ID 를 받는다. 모르는·겹치는 번호면 저장하지 않는다 */
  const parseExceptions = (): { route_id: string; minutes: number }[] | string => {
    const rows = val?.preview ?? [];
    const out: { route_id: string; minutes: number }[] = [];
    for (const tok of exceptions.split(",").map((x) => x.trim()).filter(Boolean)) {
      const i = tok.lastIndexOf(":"); const key = (i < 0 ? tok : tok.slice(0, i)).trim(); const minutes = Number(i < 0 ? NaN : tok.slice(i + 1));
      if (!key || !Number.isInteger(minutes) || minutes <= 0) return `«${tok}» — «버스 번호:분» 형식으로 쓴다 (예: 102번:12)`;
      const norm = key.replace(/번$/, "");
      const hit = rows.some((r) => r.route_id === key) ? [key] : rows.filter((r) => busNum(r) === norm).map((r) => r.route_id);
      if (!hit.length) return `«${key}» — 모르는 버스 번호다`;
      if (hit.length > 1) return `«${key}» — 같은 번호의 노선이 ${hit.length}개다. 노선 ID 로 쓴다: ${rows.filter((r) => hit.includes(r.route_id)).map((r) => `${r.route_id} = ${busNo(r)}`).join(" / ")}`;
      out.push({ route_id: hit[0], minutes });
    }
    return out;
  };
  const saveVal = () => {
    const parsed = parseExceptions();
    if (typeof parsed === "string") { setExcErr(parsed); return; }
    setExcErr(null);
    return run(async () => {
      const p = (await get<ValidityPolicyView>("/v1/admin/policies/validity", { admin: true })).policy;
      await post("/v1/admin/policies/validity", { admin: true, body: { factor: p.factor ?? 1, cap_minutes: p.cap_minutes ?? 30, default_minutes: p.default_minutes ?? 10, window_minutes: p.window_minutes ?? 1,
        route_exceptions: parsed,
        demo_on: !!p.demo_on, demo_end_at: p.demo_on ? p.demo_end_at ?? null : null } });
    }, "유효 시간 규칙 저장 — 즉시 적용");
  };
  const SOURCE_LABEL: Record<string, string> = { bis: "BIS 배차 간격", fixture: "배차표", default: "기본값 (배차 간격 모름)", exception: "노선별 예외" };
  // 예외 노선 먼저, 그다음 버스 번호 순 — 처음엔 5개만 보인다
  const previewRows = [...(val?.preview ?? [])].sort((a, b) => Number(b.validity_source === "exception") - Number(a.validity_source === "exception")
    || busNo(a).localeCompare(busNo(b), "ko", { numeric: true }) || a.route_id.localeCompare(b.route_id));
  const shownRows = showAll ? previewRows : previewRows.slice(0, 5);
  const pol = val?.policy;
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">진단 정책 설정</h1><p className="t-caption">등급 경계(적용 시작일부터) · 유효 시간 노선별 예외(즉시). 모든 값은 판본으로 남는다. 시연 모드는 시연 준비 화면에서 켜고 끈다</p></div>
      {msg && <div className="toast" role="status">{msg}</div>}
      <div className="grid grid-2">
        <section className="utility-card stack" aria-label="3.2 등급 경계값">
          <h3 className="t-body-strong">3.2 혼잡 등급 기준 {cur && <span className="t-caption muted">(현재 #{cur.policy_id}, 적용 {kstDate(cur.effective_from)})</span>}</h3>
          {sched.length > 0 && <p role="alert" className="t-caption" style={{ color: "var(--status-crowded)" }}><b>예약된 판본 {sched.length}개</b> — {sched.map((x) => `#${x.policy_id} ${kst(x.effective_from).slice(0, 16).replace("T", " ")}부터 (인원 세기 기준 ${x.count_conf_min ?? "기본값"})`).join(", ")}. 적용되면 현재 판본을 대신한다</p>}
          <table><thead><tr><th>항목</th><th>현재</th><th>새 값</th><th>검증{c(" (G8)")}</th></tr></thead><tbody>
            <tr><td>여유 하한 (잔여 %)</td><td className="num">{cur?.free_min_ratio ?? "—"}</td><td><input className="input" value={t.free_min_ratio} onChange={(e) => setT({ ...t, free_min_ratio: e.target.value })} /></td><td>{chk.range ? "통과" : <b style={{ color: "var(--status-crowded)" }}>0~100 범위</b>}</td></tr>
            <tr><td>혼잡 상한 (잔여 %)</td><td className="num">{cur?.crowded_max_ratio ?? "—"}</td><td><input className="input" value={t.crowded_max_ratio} onChange={(e) => setT({ ...t, crowded_max_ratio: e.target.value })} /></td><td>{chk.order ? "통과 (혼잡 상한 < 여유 하한)" : <b style={{ color: "var(--status-crowded)" }}>혼잡 상한 &lt; 여유 하한</b>}</td></tr>
            <tr><td>인원 세기 기준 (검출 신뢰도)</td><td className="num">{cur?.count_conf_min ?? (effConf != null ? `${effConf} (설정 기본값)` : "—")}</td><td><input className="input" value={t.count_conf_min} onChange={(e) => setT({ ...t, count_conf_min: e.target.value })} /></td><td>{chk.conf ? "통과" : <b style={{ color: "var(--status-crowded)" }}>0.05~0.95 범위</b>}</td></tr>
            <tr><td>적용 시작일 (한국 시각)</td><td>{kstDate(cur?.effective_from)}</td><td><div className="row" style={{ flexWrap: "nowrap" }}><input className="input" value={t.effective_from} onChange={(e) => setT({ ...t, effective_from: e.target.value })} /><button type="button" className="btn btn-pearl" title="실험용 — 1분 뒤부터 적용" onClick={() => setT({ ...t, effective_from: kstNowInput(60000) })}>1분 뒤</button></div></td><td>{chk.future ? "통과" : <b style={{ color: "var(--status-crowded)" }}>실패 — 과거 날짜</b>}</td></tr>
          </tbody></table>
          <div className="row"><button className="btn btn-primary" onClick={saveThr} disabled={!thrOk} aria-disabled={!thrOk} title={thrOk ? "" : `${c("G8 ")}검증 실패 항목이 있다. 해제: 값 수정`}>등급 기준 저장</button>{!thrOk && <span className="t-caption muted">사유: 검증 실패 항목{c(" (G8)")}. 해제 주체: 본인</span>}</div>
          <p className="t-caption muted">인원 세기 기준: 이 신뢰도 이상이고 발 위치가 ROI 안인 사람만 센다. 올리면 애매한 검출이 빠져 인원이 덜 흔들리지만 가려진 사람을 놓칠 수 있다. 혼잡 % = 인원 ÷ 차량 전체 정원{c(" (R22)")}</p>
          <div className="row"><span className="t-caption muted">3.5 등급 경계 변경 시{c(" SC-02")} 등급 일치율 재검증이 필요하다</span><Link className="btn btn-pearl" to="/admin/verification">정확도 검증{c(" S4")}으로 이동</Link></div>
        </section>
        <section className="utility-card stack" aria-label="3.3 유효 시간 규칙">
          <h3 className="t-body-strong">3.3 혼잡도 유효 시간</h3>
          <p className="t-caption muted">버스 안에서 잰 혼잡도를 몇 분 동안 보여 줄지 정한다. 기본은 «다음 버스가 올 때까지»(배차 간격 × 계수, 상한까지)이고, 시간이 지나면 버스 조회에 «실측 없음»으로 나온다.</p>
          <p className="t-caption">기준: 노선별 배차 간격 (BIS · 배차표) × 계수 {pol?.factor ?? "—"}, 상한 {pol?.cap_minutes ?? "—"}분 · 자료 없으면 {pol?.default_minutes ?? "—"}분 · 합산 시각 창 {pol?.window_minutes ?? "—"}분</p>
          <label className="field"><span className="t-caption">노선별 예외 (버스 번호:분, 쉼표 구분 — 예: 102번:12, 311:8)</span><input className="input" value={exceptions} onChange={(e) => { setExceptions(e.target.value); setExcErr(null); }} /></label>
          {excErr && <p className="t-caption" role="alert" style={{ color: "var(--status-crowded)" }}>{excErr}</p>}
          <button className="btn btn-primary" onClick={saveVal}>규칙 저장</button>
          {val && <table><thead><tr><th>버스</th><th>배차 간격</th><th>유효 시간</th><th>정해진 방법</th></tr></thead><tbody>{shownRows.map((p) => <tr key={p.route_id}><td>{busNo(p)}<span className="t-caption muted"> {p.route_id}</span></td><td className="num">{p.headway_minutes == null ? "자료 없음" : `${p.headway_minutes}분`}</td><td className="num"><b>{p.validity_minutes}분</b></td><td>{p.validity_source === "stale" ? <b style={{ color: "var(--status-normal)" }}>연계 장애 — 마지막 값{c(" (G12)")}</b> : SOURCE_LABEL[p.validity_source] ?? p.validity_source}</td></tr>)}</tbody></table>}
          {previewRows.length > 5 && <button type="button" className="btn btn-pearl" onClick={() => setShowAll((x) => !x)} aria-expanded={showAll}>{showAll ? "접기" : `전체 보기 (${previewRows.length}개 노선)`}</button>}
        </section>
      </div>
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
      <div style={{ marginTop: 16 }}><HistoryPanel title="등급 기준 이력" rows={thr.map((x) => ({ ...x, superseded_at: x.is_current ? null : "-" })) as unknown as Record<string, unknown>[]} columns={[{ key: "policy_id", label: "#" }, { key: "free_min_ratio", label: "여유 하한" }, { key: "crowded_max_ratio", label: "혼잡 상한" }, { key: "count_conf_min", label: "인원 세기 기준" }, { key: "effective_from", label: "적용 시작", fmt: (x) => fmtTime(String(x)) }, { key: "created_by", label: "등록자" }]} /></div>
    </>
  );
}
