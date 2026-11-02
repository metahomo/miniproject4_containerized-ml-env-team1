/* S8 시연 준비·수행 — 8.1→8.4 순서 레일 (U7). 앞 단계 미완료면 뒤 단계 잠금 + 게이트 ID.
   8.1 «102번 운행 차량으로 다시 연결»(T097): 실제 BIS 에서 충남대학교에 곧 도착할 차량 순서대로 CAM-DEMO-01~03 을 다시 연결한다.
   2026-09-30 삭제: 차량·카메라를 손으로 넣던 8.1 매핑 표(BIS 재연결이 매핑을 바꿈 — 지금 연결은 읽기 전용으로 보여 준다),
   8.3 사전 촬영 프레임 일괄 등록(S6 실측 등록을 여러 번 하는 것과 같음 — S6 로 보낸다). 레일 5단계 → 4단계. */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, fmtTime, get, post, type GateError, kstInputToUtc } from "../../api/client";
import type { Mapping, ValidityPolicyView } from "../../api/types";
import { GateBlock } from "../../components/GateBlock";
import { refreshDemo, useDemo } from "../../stores/demo";
import { useCodes } from "../../stores/auth";

interface RemapRow { camera_id: string; before: string | null; after: string | null; expected_arrival_at: string | null; action: "kept" | "changed" | "unchanged" }
interface RemapResult { route_id: string; stop_id: string; source_status: string; changed: number; message: string; rows: RemapRow[] }
const DEMO_STOPS = [{ id: "30300037:42620", name: "충남대학교 (홈플러스유성점 방면)" }, { id: "30300037:42600", name: "충남대학교 (온천교 방면)" }];
const kst = (iso?: string | null) => (iso ? new Date(iso.replace("Z", "") + "Z").toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Seoul" }) : "—");
const ACTION: Record<string, string> = { kept: "그대로 (곧 도착)", changed: "다시 연결", unchanged: "변경 없음" };
const DEMO_CAMS = ["CAM-DEMO-01", "CAM-DEMO-02", "CAM-DEMO-03"];

export default function Demo() {
  const c = useCodes();   // 설계 번호는 화면에 보이지 않게 (2026-09-30)
  const demo = useDemo();
  const [maps, setMaps] = useState<Mapping[]>([]);
  const [endAt, setEndAt] = useState("");
  const [gate, setGate] = useState<GateError | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [remapStop, setRemapStop] = useState(DEMO_STOPS[0].id);
  const [remap, setRemap] = useState<RemapResult | null>(null);
  const load = useCallback(() => get<Mapping[]>("/v1/admin/mappings", { admin: true }).then(setMaps).catch(() => undefined), []);
  const doRemap = async () => {
    setBusy("remap"); setGate(null); setRemap(null);
    try { setRemap(await post<RemapResult>("/v1/admin/demo/bis-remap", { admin: true, body: { route_id: "30300037", stop_id: remapStop, camera_ids: DEMO_CAMS } })); await load(); }
    catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : { gate: "—", reason_code: "ERROR", reason: (e as Error).message, resolver_role: "self" }); }
    finally { setBusy(null); }
  };
  useEffect(() => { load(); }, [load]);

  const vehicleOf = (cam: string) => maps.find((m) => m.camera_id === cam)?.vehicle_id;
  const s1 = !!vehicleOf(DEMO_CAMS[0]) && !!vehicleOf(DEMO_CAMS[1]);   // 앞차·다음 차 카메라가 차량에 연결돼 있다
  const s2 = s1 && demo.on;
  // 시연 모드만 바꾼다 — 계수·상한·기본값·합산 창·노선별 예외(S3 3.3)는 저장 직전의 현재 판본 그대로 보낸다
  // (2026-09-30 — 이전: 계수 1.0·상한 30·예외 30300037:12 를 고정값으로 보내 S3 에서 바꾼 값을 덮어썼다)
  const turn = async (on: boolean) => {
    setBusy("demo"); setGate(null);
    try {
      const p = (await get<ValidityPolicyView>("/v1/admin/policies/validity", { admin: true })).policy;
      await post("/v1/admin/policies/validity", { admin: true, body: {
        factor: p.factor ?? 1, cap_minutes: p.cap_minutes ?? 30, default_minutes: p.default_minutes ?? 10, window_minutes: p.window_minutes ?? 1,
        route_exceptions: (p.route_exceptions ?? []).map((e) => ({ route_id: e.route_id, minutes: e.minutes })),
        demo_on: on, demo_end_at: on && endAt ? kstInputToUtc(endAt) : null } });
      await refreshDemo();
    } catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : null); } finally { setBusy(null); }
  };
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">시연 준비 · 수행</h1><p className="t-caption">시연 모드를 켜기 전에 실측을 등록하면 사전 촬영 프레임이 만료 처리되어 시연이 '실측 없음'만 보여 준다 — 순서를 강제한다{c(" (SD_01 §11-3)")}</p></div>
      {gate && <div style={{ marginBottom: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
      <div className="grid grid-2">
        <section className="utility-card stack" aria-label="8.1 운행 차량 연결">
          <h3 className="t-body-strong">8.1 102번 운행 차량 연결{c(" (G9)")}</h3>
          <table><thead><tr><th>순서</th><th>카메라</th><th>지금 연결된 차량</th></tr></thead>
            <tbody>{DEMO_CAMS.map((cam, i) => <tr key={cam}><td>{["앞차", "다음 차", "흐린 차량"][i]}</td><td>{cam}</td><td>{vehicleOf(cam) ? <b>{vehicleOf(cam)}</b> : <b className="status status-crowded">연결 없음{c(" (G9)")}</b>}</td></tr>)}</tbody></table>
          <div className="stack" style={{ borderTop: "var(--border-hairline)", paddingTop: 12 }}>
            <div className="row">
              <select className="input" style={{ width: 240 }} value={remapStop} onChange={(e) => setRemapStop(e.target.value)} aria-label="시연 정류장">
                {DEMO_STOPS.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <button className="btn btn-primary" onClick={doRemap} disabled={busy === "remap"}>{busy === "remap" ? "BIS 조회 중…" : "102번 운행 차량으로 다시 연결"}</button>
            </div>
            <span className="t-caption muted">실제 BIS 에서 이 정류장에 곧 도착할 102번 차량 순서대로 CAM-DEMO-01~03 을 연결한다. 이미 곧 도착할 차량에 연결된 카메라는 그대로 둔다. 운행 시간 밖이면 바꾸지 않는다. 시연 직전·도착 버스가 바뀌면 다시 누른다</span>
            {remap && (
              <>
                <p className="t-caption"><b>{remap.message}</b> · 연계 {remap.source_status}</p>
                <table><thead><tr><th>카메라</th><th>이전</th><th>지금</th><th>도착 예정 (KST)</th><th>처리</th></tr></thead>
                  <tbody>{remap.rows.map((r) => <tr key={r.camera_id}><td>{r.camera_id}</td><td>{r.before ?? "—"}</td><td><b>{r.after ?? "—"}</b></td><td>{kst(r.expected_arrival_at)}</td><td>{ACTION[r.action] ?? r.action}</td></tr>)}</tbody></table>
              </>
            )}
          </div>
          <div className="row"><button className="btn btn-pearl" onClick={load}>재확인</button>{!s1 && <span className="t-caption muted">사유: 앞차·다음 차 카메라에 연결된 차량이 없다. 해제: 위 «다시 연결» 또는{c(" S2 2.4")} 투입 등록의 매핑</span>}</div>
        </section>
        <section className="utility-card stack" aria-label="8.2 시연 모드 켜기">
          <h3 className="t-body-strong">8.2 시연 모드 켜기{c(" (G14)")}</h3>
          <label className="field"><span className="t-caption">종료 예정 시각 (한국 시각, 비우면 켠 시각 + 2시간)</span><input className="input" value={endAt} onChange={(e) => setEndAt(e.target.value)} placeholder="2026-09-28T16:00:00" disabled={!s1} /></label>
          <div className="row"><button className="btn btn-primary" onClick={() => turn(true)} disabled={!s1 || demo.on || busy === "demo"} aria-disabled={!s1 || demo.on} title={!s1 ? "8.1 미완료 — 순서 강제" : demo.on ? "이미 켜짐" : ""}>시연 모드 켜기</button>{!s1 && <span className="t-caption muted">사유: 8.1 미완료 — 순서 강제{c(" (SD_01 §11-3)")}</span>}{demo.on && <span className="chip">켜짐 · 자동 해제 {fmtTime(demo.endAt)}</span>}</div>
        </section>
        <section className="utility-card stack">
          <h3 className="t-body-strong">8.3 실측 등록 · 시연 수행 · 8.4 끄기</h3>
          <div className="row">
            <Link className="btn btn-secondary" to={`/admin/measurements?camera_id=${DEMO_CAMS[0]}`} aria-disabled={!s2} onClick={(e) => !s2 && e.preventDefault()} title={!s2 ? `시연 모드 꺼짐 — 등록해도 만료로 '실측 없음'${c(" (G14)")}` : ""}>실측 등록{c(" S6")} (사전 촬영 프레임)</Link>
            <Link className="btn btn-primary" to="/?route_id=30300037&stop_id=30300037:42620" aria-disabled={!s2} onClick={(e) => !s2 && e.preventDefault()} title={!s2 ? "8.2 미완료" : ""}>버스 조회 열기 (102번 · 충남대학교)</Link>
            {!s2 && <span className="t-caption muted">사유: 시연 모드 꺼짐 — 등록해도 만료로 '실측 없음'{c(" (G14)")}</span>}
          </div>
          <div className="row"><button className="btn btn-dark-utility" onClick={() => turn(false)} disabled={!demo.on || busy === "demo"} aria-disabled={!demo.on}>시연 모드 끄기</button><span className="t-caption muted">끄지 않으면 종료 예정 시각에 자동 해제{c(" (P0 0.4)")} — 그 전까지 실운영 응답에 시연 표시가 남는다</span></div>
        </section>
      </div>
    </>
  );
}
