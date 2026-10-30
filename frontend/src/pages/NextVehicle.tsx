/* S7 버스 조회 (후속 차량 여유도, UC2 — T103 이름 변경) — 정류장으로 찾기. 표 + 근거 유형 3값, 조회 불가(G12)·기준 정보 없음(G11) 블록, 30초 갱신.
   T099: 이용자는 카메라 번호·내부 코드를 몰라도 된다 — 노선·정류장은 이름으로 고른다(대전 BIS 전체).
   2026-09-30 삭제: «버스 번호로 찾기»(번호판 조회 — 시민은 번호판을 모르고, 결과가 정류장 표의 한 줄과 겹쳤다).
   T102: 수동 조회 — «조회»를 누를 때만 BIS 를 부른다(열어 두기만 해도 30초마다 부르던 것이 공공데이터포털 일일 한도를 넘겼다).
   조회 후에는 화면 시계로 "마지막 조회 N분 전"·"약 N분 후"를 스스로 줄이고(서버 호출 없음), 3분이 지나면 다시 조회를 권한다.
   «자동 갱신»은 선택: 30초 간격, 5분 뒤 자동으로 꺼지고, 다른 탭에 가 있으면 부르지 않는다.
   T109: 노선 선택 ↔ 정류장 선택이 서로 거른다 — 노선을 고르면 그 노선의 정류장만, 정류장을 먼저 고르면 그 정류장에 서는
   노선만(/v1/reference/stops/{stop_id}/routes) 고를 수 있다. 둘 다 고르면 그 노선의 그 정류장으로 조회한다.
   2026-09-30 홈 = 이 화면: 이용자에게 필요한 건 «언제 오나 + 얼마나 찼나» 둘뿐 — 버스마다 한 줄. 진행 레일·설명문 삭제.
   근거·커버리지·유효 시간 표는 관제·운영 계정에게만 «자세히»로 접어 둔다. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, fmtTime, get, minutesAgo, minutesFromNow, type GateError, hhmm } from "../api/client";
import type { NextVehicleItem, NextVehicleResponse, RouteRef, StopRef } from "../api/types";
import { isStaff, useCodes, usePerms } from "../stores/auth";
import { GateBlock } from "../components/GateBlock";
import { SourceDrawer } from "../components/SourceDrawer";
import { StatusBadge, seatHint } from "../components/StatusBadge";
import { WarningChips } from "../components/WarningChips";
import { useReadiness } from "../stores/readiness";

// 시연 기본값: 102번 · 충남대학교 (홈플러스유성점 방면). 목록은 /v1/reference/routes·stops (실제 대전 BIS 전체)
const DEFAULT_ROUTE = "30300037";
const DEFAULT_STOP = "30300037:42620";
const STALE_MS = 3 * 60 * 1000;          // 이만큼 지나면 "다시 조회" 권고
const AUTO_EVERY_MS = 30 * 1000;         // 자동 갱신 간격
const AUTO_FOR_MS = 5 * 60 * 1000;       // 자동 갱신은 켠 뒤 5분 동안만
const ago = (ms: number) => (ms < 60000 ? `${Math.max(0, Math.floor(ms / 1000))}초 전` : `${Math.floor(ms / 60000)}분 ${Math.floor((ms % 60000) / 1000)}초 전`);
const headcount = (v: { persons_sum?: number | null; capacity?: number | null }) =>
  v.persons_sum != null && v.capacity ? `${v.persons_sum} / ${v.capacity}명` : v.persons_sum != null ? `${v.persons_sum}명` : "—";

/** 같은 정류장인지 가르는 열쇠 — BIS 는 `노선ID:정류소ID` 의 정류소 ID, 고정 자료는 정류장 이름 */
export const stopKey = (x: { stop_id: string; stop_name: string }) => (x.stop_id.includes(":") ? x.stop_id.split(":")[1] : x.stop_name);

export default function NextVehicle() {
  const c = useCodes();   // 설계 번호는 운영 관리자에게만
  const staff = isStaff(usePerms());   // 상세 표(근거·커버리지·유효 시간)는 관제·운영 계정만
  const [sp] = useSearchParams();
  const { ready } = useReadiness();
  const initQ = sp.get("q") ?? "";
  // 고른 버스(노선)와 고른 정류장. 정류장은 대표 stop_id 로 기억한다 — 같은 정류소면 노선이 달라도 같은 정류장이다
  const [routeId, setRouteId] = useState(sp.get("route_id") ?? (initQ ? "" : DEFAULT_ROUTE));
  const [pickStop, setPickStop] = useState<string>(sp.get("stop_id") ?? (initQ ? "" : DEFAULT_STOP));
  const [routes, setRoutes] = useState<RouteRef[]>([]);
  const [routeQ, setRouteQ] = useState("");
  const [stops, setStops] = useState<StopRef[]>([]);                   // 고른 노선의 정류장
  const [stopRoutes, setStopRoutes] = useState<StopRef[]>([]);         // 고른 정류장에 서는 노선 (노선별 stop_id)
  const [stopQ, setStopQ] = useState(initQ);
  const [found, setFound] = useState<StopRef[]>([]);                   // 노선을 안 골랐을 때: 정류장 이름으로 전체 검색

  // 헤더 검색으로 같은 화면에서 검색어만 바뀌면 그 이름으로 다시 찾는다
  useEffect(() => { if (initQ) { setRouteId(""); setPickStop(""); setStopQ(initQ); } }, [initQ]);
  useEffect(() => { get<RouteRef[]>("/v1/reference/routes").then(setRoutes).catch(() => undefined); }, []);
  useEffect(() => {
    if (!routeId) { setStops([]); return; }
    get<StopRef[]>("/v1/reference/stops", { query: { route_id: routeId, limit: 500 } }).then(setStops).catch(() => setStops([]));
  }, [routeId]);
  useEffect(() => {
    if (!pickStop) { setStopRoutes([]); return; }
    get<StopRef[]>(`/v1/reference/stops/${encodeURIComponent(pickStop)}/routes`).then(setStopRoutes).catch(() => setStopRoutes([]));
  }, [pickStop]);
  useEffect(() => {   // 노선을 안 골랐으면 정류장 이름으로 전체에서 찾는다 (기준 정보 조회 — BIS 호출 아님)
    if (routeId || !stopQ.trim()) { setFound([]); return; }
    const t = window.setTimeout(() => {
      get<StopRef[]>("/v1/reference/stops", { query: { q: stopQ.trim(), limit: 500 } }).then(setFound).catch(() => setFound([]));
    }, 250);
    return () => window.clearTimeout(t);
  }, [stopQ, routeId]);
  const pickKey = pickStop ? stopKey({ stop_id: pickStop, stop_name: stopRoutes[0]?.stop_name ?? "" }) : "";
  const pickName = stopRoutes.find((x) => x.stop_id === pickStop)?.stop_name ?? stops.find((x) => x.stop_id === pickStop)?.stop_name ?? found.find((x) => x.stop_id === pickStop)?.stop_name ?? pickStop;
  // 조회에 쓰는 정류장 = 고른 노선에서의 그 정류장
  const stopId = routeId && pickStop ? (stopRoutes.find((x) => x.route_id === routeId)?.stop_id ?? (pickStop.startsWith(routeId + ":") || stops.some((x) => x.stop_id === pickStop) ? pickStop : "")) : "";
  const routeName = (routes.find((r) => r.route_id === routeId) ?? stopRoutes.find((r) => r.route_id === routeId))?.route_no ?? routeId;
  // 버스 번호 목록: 정류장을 골랐으면 그 정류장에 서는 노선만
  const routeList: { route_id: string; route_no: string }[] = pickStop ? stopRoutes : routes;
  const shownRoutes = routeList.filter((r) => !routeQ.trim() || r.route_no.includes(routeQ.trim()) || r.route_id === routeQ.trim());
  // 정류장 목록: 버스를 골랐으면 그 노선의 정류장만, 아니면 이름 검색 결과(같은 정류소는 하나로)
  const stopList: (StopRef & { n?: number })[] = routeId
    ? stops.filter((x) => !stopQ.trim() || x.stop_name.split(" (")[0].includes(stopQ.trim()))   // "(○○ 방면)" 은 빼고 정류장 이름으로
    : Object.values(found.reduce<Record<string, StopRef & { n: number }>>((acc, x) => {
        const k = stopKey(x); acc[k] = acc[k] ? { ...acc[k], n: acc[k].n + 1 } : { ...x, n: 1 }; return acc;
      }, {}));
  // 선택 상자에 보이는 정류장 = 목록 안에서 고른 정류장과 같은 정류소인 항목
  const pickSel = pickStop ? (stopList.find((x) => stopKey(x) === pickKey)?.stop_id ?? pickStop) : "";
  // 고르면 반대쪽 검색어는 비운다 — 고른 것에 맞는 목록 전체를 보여 준다
  const pickRoute = (id: string) => { setRouteId(id); if (id) setStopQ(""); };
  const pickStopById = (id: string) => { setPickStop(id); if (id) setRouteQ(""); };
  const [data, setData] = useState<NextVehicleResponse | null>(null);
  const [gate, setGate] = useState<GateError | null>(null);
  const [sel, setSel] = useState<NextVehicleItem | null>(null);
  const [busy, setBusy] = useState(false);

  const [fetchedLocal, setFetchedLocal] = useState<number | null>(null);   // 이 브라우저가 마지막으로 조회한 시각
  const [now, setNow] = useState(Date.now());
  const [autoUntil, setAutoUntil] = useState<number | null>(null);
  const load = useCallback(async (r: string = routeId, st: string = stopId) => {
    if (!ready || !r || !st) return;
    setBusy(true); setGate(null);
    try { setData(await get<NextVehicleResponse>("/v1/next-vehicle", { query: { route_id: r, stop_id: st, limit: 4 } })); setFetchedLocal(Date.now()); }
    catch (e) { setData(null); setFetchedLocal(null); setGate(e instanceof ApiError && e.gate ? e.gate : { gate: "—", reason_code: "ERROR", reason: (e as Error).message, resolver_role: "self" }); }
    finally { setBusy(false); }
  }, [routeId, stopId, ready]);
  // 화면 시계 — "N분 전"·"약 N분 후"를 줄이기만 한다 (서버 호출 없음)
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  // 노선·정류장을 바꾸면 이전 결과는 치운다 — 다른 정류장 결과를 보여 주지 않게
  useEffect(() => { setData(null); setFetchedLocal(null); setAutoUntil(null); }, [routeId, stopId]);
  // 링크로 노선·정류장이 지정돼 들어온 경우(S8 «시연 수행» 등)만 준비되면 1번 조회 — 그 링크를 누른 것이 조회 요청이다
  const linked = useRef(!!(sp.get("route_id") && sp.get("stop_id")));
  useEffect(() => { if (linked.current && ready && stopId) { linked.current = false; load(); } }, [ready, load, stopId]);
  // 선택 «자동 갱신»: 30초 간격, 5분 뒤 꺼짐, 탭이 가려져 있으면 건너뜀
  useEffect(() => {
    if (!autoUntil) return;
    const t = window.setInterval(() => {
      if (Date.now() >= autoUntil) { setAutoUntil(null); return; }
      if (!document.hidden) load();
    }, AUTO_EVERY_MS);
    return () => window.clearInterval(t);
  }, [autoUntil, load]);
  const age = fetchedLocal ? now - fetchedLocal : null;
  const stale = age != null && age > STALE_MS && !autoUntil;

  const unavailable = data && data.source_status !== "ok";
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">버스 조회</h1><p className="t-caption">타려는 버스가 언제 오는지, 얼마나 찼는지</p></div>
      {!ready && <div className="gate output" role="status" style={{ marginBottom: 12 }}>지금은 조회할 수 없다 — 서버 준비 중. 잠시 뒤 다시 연다.</div>}
      <form className="utility-card stack" onSubmit={(e) => { e.preventDefault(); load(); }} aria-label="버스 조회 조건">
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field" style={{ width: 110 }}><span className="t-caption">버스 번호 검색</span>
            <input className="input" value={routeQ} onChange={(e) => setRouteQ(e.target.value)} placeholder="예: 102" /></label>
          <label className="field" style={{ minWidth: 150 }}><span className="t-caption">버스 ({shownRoutes.length})</span>
            <select className="input" aria-label="노선" value={routeId} onChange={(e) => pickRoute(e.target.value)}>
              <option value="">버스 선택</option>
              {routeId && !shownRoutes.some((r) => r.route_id === routeId) && <option value={routeId}>{routeName}</option>}
              {shownRoutes.map((r) => <option key={r.route_id} value={r.route_id} title={r.route_id}>{r.route_no}</option>)}
            </select></label>
          <label className="field" style={{ width: 140 }}><span className="t-caption">정류장 검색</span>
            <input className="input" value={stopQ} onChange={(e) => setStopQ(e.target.value)} placeholder="예: 충남대" /></label>
          <label className="field" style={{ minWidth: 240, flex: 1 }}><span className="t-caption">정류장 ({stopList.length})</span>
            <select className="input" aria-label="정류장" value={pickSel} onChange={(e) => pickStopById(e.target.value)}>
              <option value="">{routeId || stopQ.trim() ? "정류장 선택" : "정류장 이름을 입력하거나 버스를 고른다"}</option>
              {pickStop && !stopList.some((x) => x.stop_id === pickSel) && <option value={pickSel}>{pickName}</option>}
              {stopList.map((x) => <option key={x.stop_id} value={x.stop_id} title={x.stop_id}>{x.stop_name}{x.n ? ` · 버스 ${x.n}개` : ""}</option>)}
            </select></label>
          <button className="btn btn-primary" disabled={!ready || busy || !stopId} title={!ready ? `준비 중${c(" (G0)")}` : !stopId ? "버스와 정류장을 모두 고른다" : ""}>조회</button>
          {(routeId || pickStop) && <button type="button" className="btn btn-pearl" onClick={() => { setRouteId(""); setPickStop(""); setRouteQ(""); setStopQ(""); }}>처음부터</button>}
        </div>
      </form>
      <div className="row t-caption" style={{ marginTop: 12 }} aria-live="polite">
        {fetchedLocal ? <span>마지막 조회 <b>{ago(age ?? 0)}</b></span> : <span className="muted">버스와 정류장을 고르고 «조회»를 누른다</span>}
        {fetchedLocal && <button type="button" className="btn btn-pearl" style={{ minHeight: 30 }} onClick={() => load()} disabled={!ready || busy}>{busy ? "조회 중…" : "다시 조회"}</button>}
        <label className="chip" title="30초마다 다시 조회하고 5분 뒤 자동으로 꺼진다. 다른 탭에 가 있으면 부르지 않는다">
          <input type="checkbox" checked={!!autoUntil} disabled={!ready || !stopId} onChange={(e) => { if (e.target.checked) { setAutoUntil(Date.now() + AUTO_FOR_MS); if (!fetchedLocal) load(); } else setAutoUntil(null); }} />
          &nbsp;자동 갱신{autoUntil ? ` · ${Math.max(0, Math.ceil((autoUntil - now) / 60000))}분 뒤 꺼짐` : " (5분)"}
        </label>
      </div>
      {stale && (
        <div className="gate output" style={{ marginTop: 12 }} role="status">
          <b>정보가 {Math.floor((age ?? 0) / 60000)}분 지났다</b> — 도착 예정은 화면에서 줄여 보이지만 실제 위치는 바뀌었을 수 있다.{" "}
          <button type="button" className="btn btn-secondary" style={{ minHeight: 30 }} onClick={() => load()} disabled={!ready || busy}>다시 조회</button>
        </div>
      )}
      {data && !unavailable && (
        <section className="stack" style={{ marginTop: 16 }} aria-label="조회 결과">
          <h2 className="t-body-strong">{routeName} · {pickName.split(" (")[0]}</h2>
          {data.vehicles.length === 0 && <p className="muted">다가오는 버스가 없다</p>}
          <ul className="bus-list">
            {data.vehicles.map((v, i) => {
              const m = minutesFromNow(v.expected_arrival_at); const measured = v.basis_type === "measured";
              return (
                <li key={i} className="bus-item">
                  <div>
                    <div className="when">{m === null ? "도착 정보 없음" : m <= 0 ? "곧 도착" : `약 ${m}분 후`}</div>
                    <span className="t-caption muted">{hhmm(v.expected_arrival_at) ?? ""}{v.vehicle_id ? ` · ${v.vehicle_id}` : ""}</span>
                  </div>
                  <div className="fill">
                    {measured ? <>
                      <StatusBadge level={v.crowding_level} suffix={seatHint(v.crowding_level)} />
                      <span className="t-caption">남은 공간 <b>{v.vacant_ratio?.toFixed(0) ?? "—"}%</b>{v.persons_sum != null ? ` · ${headcount(v)}` : ""}</span>
                    </> : <span className="t-caption muted">혼잡 정보 없음</span>}
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="t-caption muted">{data.notice}</p>
          {staff && (
            <details className="utility-card">
              <summary className="t-caption">자세히 (관제용 — 근거·커버리지·유효 시간)</summary>
              <table style={{ marginTop: 8 }}>
                <thead><tr><th scope="col">차량</th><th scope="col">도착 예정</th><th scope="col">인원 / 정원</th><th scope="col">잔여 %</th><th scope="col">등급</th><th scope="col">근거</th><th scope="col">실측 시각</th><th scope="col">커버리지 · 경고</th></tr></thead>
                <tbody>
                  {data.vehicles.map((v, i) => {
                    const m = minutesFromNow(v.expected_arrival_at); const ago = minutesAgo(v.measured_at); const measured = v.basis_type === "measured";
                    return (
                      <tr key={i} onClick={() => setSel(v)} style={{ cursor: "pointer" }} title="클릭: 근거 보기">
                        <td><b>{v.vehicle_id ?? "—"}호</b></td>
                        <td>{m === null ? "—" : m <= 0 ? `곧 도착·지남 (${hhmm(v.expected_arrival_at)})` : `약 ${m}분 후 ${hhmm(v.expected_arrival_at)}`}</td>
                        <td className="num"><b>{measured ? headcount(v) : "—"}</b></td>
                        <td className="num">{measured ? (v.crowding_level === "uncertain" ? `참고 ${v.vacant_ratio?.toFixed(0)}` : v.vacant_ratio?.toFixed(0)) : "—"}</td>
                        <td>{measured ? <StatusBadge level={v.crowding_level} suffix={seatHint(v.crowding_level)} /> : <StatusBadge level="no_measurement" />}</td>
                        <td>{measured ? "실측" : "실측 없음"}</td>
                        <td>{measured ? `${hhmm(v.measured_at)} (${ago}분 전)` : "—"}</td>
                        <td>{measured ? <span className="row">{v.coverage_num}/{v.coverage_den} <WarningChips warnings={v.warnings} /></span> : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="t-caption muted">적용 유효 시간: 노선 {data.route_id} = {data.applied_validity_minutes}분 ({data.validity_source}) · 조회 {fmtTime(data.fetched_at)}</p>
            </details>
          )}
        </section>
      )}
      {unavailable && data && (
        <div style={{ marginTop: 16 }}>
          <GateBlock error={{ gate: "G12", reason_code: data.source_status.toUpperCase(), reason: `${staff ? "후속 차량 정보 조회 불가" : "도착 정보를 받을 수 없다"} — ${data.source_status === "timeout" ? "운행 정보 응답 지연" : data.source_status === "no_vehicle" ? "다음 차량 없음 (막차 이후 등)" : data.source_status === "rate_limited" ? (staff ? "대전 BIS 하루 호출 한도 초과 — 한국 시각 자정에 초기화되며, 그때까지 도착 정보를 받을 수 없다. 운영 관리자: 공공데이터포털에서 트래픽 증가(운영계정) 신청" : "오늘 조회 한도를 넘었다 — 자정 이후 다시 조회한다") : "BIS 운행 정보 연계 장애"}${staff ? `. 현재 프레임 진단${c(" S5")}은 정상이다${c(" (NFR-08)")}. 다음 요청 시 자동 재시도` : ""}`, resolver_role: "external", gate_event_id: null }}
            extra={staff ? <Link className="btn btn-secondary" to="/diagnose">현재 프레임 진단{c(" S5")}</Link> : undefined} />
        </div>
      )}
      {staff && data?.demo_mode && <div className="chip" style={{ marginTop: 16 }}><b>시연 모드</b> — 사전 촬영 프레임을 등록 시각 기준으로 유효 처리한 값이다</div>}
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} retryLabel="식별자 수정" /></div>}
      {sel && (
        <SourceDrawer title={`${sel.vehicle_id ?? "—"}호 근거`} onClose={() => setSel(null)}>
          <dl>
            <dt>근거 유형</dt><dd>{sel.basis_type === "measured" ? "실측" : sel.basis_type === "no_measurement" ? "실측 없음 — 등급·비율을 비운다" : "조회 불가"}</dd>
            <dt>도착 예정</dt><dd>{fmtTime(sel.expected_arrival_at)}</dd>
            <dt>실측 시각</dt><dd>{fmtTime(sel.measured_at)}</dd>
            <dt>적용 유효 시간</dt><dd>{data?.applied_validity_minutes}분 ({data?.validity_source})</dd>
            <dt>커버리지</dt><dd>{sel.coverage_num != null ? `${sel.coverage_num}/${sel.coverage_den} (합산 카메라/매핑 카메라)` : "—"}</dd>
            <dt>경고</dt><dd>{sel.warnings.length ? sel.warnings.map((w, i) => <div key={i}><code>{w.code}</code> {w.detail}</div>) : "없음"}</dd>
            <dt>시연 모드</dt><dd>{data?.demo_mode ? "예" : "아니오"}</dd>
          </dl>
        </SourceDrawer>
      )}
    </>
  );
}
