/* S2 카메라·차량 투입 등록 — 2.1 카메라 선택·현황·등록, 탭 ROI / 제원 / 매핑(자동완성). G3·G8·G9·G12 블록.
   2026-09-30 삭제: ROI 바닥 면적·발자국 보정 칸(R22 뒤 계산에 안 씀), CSV 일괄 매핑(카메라 몇 대 · S8 BIS 재연결이 매핑을 바꿈), 이력 탭(읽기 전용, 볼 일 드묾). */
import { useCallback, useEffect, useState } from "react";
import { PLACE_TYPES, placeLabel } from "../../api/place";
import { ApiError, del, get, post, type GateError, kstInputToUtc, kstNowInput } from "../../api/client";
import type { CameraStatus, Mapping, Roi } from "../../api/types";
import { GateBlock } from "../../components/GateBlock";
import { PolygonEditor } from "../../components/PolygonEditor";
import { useCodes } from "../../stores/auth";

type Tab = "roi" | "spec" | "map";
const today = () => kstNowInput();   // 입력칸은 한국 시각, 보낼 때 UTC
/** 화면 전체 ROI — 진단 API 가 받는 가장 큰 프레임(긴 변 4096px)을 덮는다. R22 에서 ROI 는 셀 사람을 거르는 역할만 한다 */
const FULL_FRAME_ROI = [[0, 0], [4096, 0], [4096, 4096], [0, 4096]];

export default function Onboarding() {
  const c = useCodes();   // 설계 번호는 화면에 보이지 않게 (2026-09-30)
  const [cams, setCams] = useState<CameraStatus[]>([]);
  const [camId, setCamId] = useState("");
  const [cam, setCam] = useState<CameraStatus | null>(null);
  const [tab, setTab] = useState<Tab>("roi");
  const [gate, setGate] = useState<GateError | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  // 카메라 등록
  const [nc, setNc] = useState({ camera_id: "", place_type: "bus_in", route_id: "30300037", stop_id: "", vehicle_type_id: "VT_LOW" });
  // ROI
  const [pts, setPts] = useState<number[][]>([]);
  const [effFrom, setEffFrom] = useState(today());
  const [bg, setBg] = useState<string | null>(null);
  const [rois, setRois] = useState<Roi[]>([]);
  // 제원
  const [spec, setSpec] = useState({ capacity: "80", seat_count: "30", source: "제조사 제원표" });
  // 매핑
  const [fleet, setFleet] = useState<{ vehicle_id: string; vehicle_type_id?: string | null }[]>([]);
  const [fleetStatus, setFleetStatus] = useState("ok");
  const [veh, setVeh] = useState("");
  const [maps, setMaps] = useState<Mapping[]>([]);

  const loadCams = useCallback(() => get<CameraStatus[]>("/v1/admin/cameras", { admin: true }).then(setCams).catch(() => undefined), []);
  const loadCam = useCallback(async (id: string) => {
    if (!id) { setCam(null); return; }
    try {
      setCam(await get<CameraStatus>(`/v1/admin/cameras/${id}`, { admin: true }));
      setRois(await get<Roi[]>(`/v1/admin/cameras/${id}/roi`, { admin: true }));
      setMaps(await get<Mapping[]>("/v1/admin/mappings", { admin: true }));
    } catch (e) { if (e instanceof ApiError && e.gate) setGate(e.gate); }
  }, []);
  useEffect(() => { loadCams(); }, [loadCams]);
  useEffect(() => { loadCam(camId); }, [camId, loadCam]);
  useEffect(() => { if (cam?.capacity != null) setSpec((sp) => ({ ...sp, capacity: String(cam.capacity) })); }, [cam?.camera_id, cam?.capacity]);   // 현재 정원을 입력란에
  useEffect(() => {
    const rid = cam?.route_id; if (!rid) { setFleet([]); return; }
    get<{ source_status: string; vehicles: { vehicle_id: string; vehicle_type_id?: string | null }[] }>("/v1/admin/fleet", { admin: true, query: { route_id: rid, q: veh || undefined } })
      .then((f) => { setFleet(f.vehicles); setFleetStatus(f.source_status); }).catch(() => setFleetStatus("unavailable"));
  }, [cam?.route_id, veh]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setGate(null); setMsg(null);
    try { await fn(); setMsg(ok); await loadCams(); await loadCam(camId); }
    catch (e) { setGate(e instanceof ApiError && e.gate ? e.gate : { gate: "—", reason_code: "ERROR", reason: (e as Error).message, resolver_role: "self" }); }
  };
  const registerCamera = () => run(async () => { await post("/v1/admin/cameras", { admin: true, body: { ...nc, stop_id: nc.stop_id || null, vehicle_type_id: nc.vehicle_type_id || null, route_id: nc.route_id || null } }); setCamId(nc.camera_id); }, `카메라 ${nc.camera_id} 등록`);
  const saveRoi = () => run(() => post(`/v1/admin/cameras/${camId}/roi`, { admin: true, body: { polygon: pts, effective_from: kstInputToUtc(effFrom) } }), "ROI 저장 — roi_stale 해제");
  const saveSpec = () => run(() => post(`/v1/admin/vehicle-types/${cam?.vehicle_type_id}/spec`, { admin: true, body: { capacity: Number(spec.capacity), seat_count: spec.seat_count ? Number(spec.seat_count) : null, source: spec.source, effective_from: kstInputToUtc(effFrom) } }), "제원 저장");
  const saveMap = () => run(() => post("/v1/admin/mappings", { admin: true, body: { camera_id: camId, vehicle_id: veh, vehicle_type_id: cam?.vehicle_type_id ?? null } }), `매핑 저장 ${camId} ↔ ${veh}`);
  const releaseMap = (id: number) => run(() => del(`/v1/admin/mappings/${id}`, { admin: true }), "매핑 해제 — 해당 차량 실측은 '실측 없음'");

  const myMap = maps.find((m) => m.camera_id === camId);
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">카메라 · 차량 투입 등록</h1><p className="t-caption">ROI{c("(UC6)")} · 차량 제원{c("(UC7)")} · 차량 번호 매핑{c("(UC12)")}. 카메라 한 대를 투입하는 일을 한자리에서 한다</p></div>
      <section className="utility-card stack" aria-label="2.1 카메라 선택">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <label className="field" style={{ minWidth: 320 }}><span className="t-caption">2.1 카메라</span>
            <select className="input" value={camId} onChange={(e) => setCamId(e.target.value)}><option value="">선택</option>{cams.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {c.place_type === "bus_in" ? "버스 차내" : "승강장"} · {c.route_id ?? "—"}</option>)}</select></label>
          <details><summary className="btn btn-dark-utility" style={{ display: "inline-flex" }}>카메라 등록{c(" (G3 해제)")}</summary>
            <div className="row" style={{ marginTop: 12 }}>
              <input className="input" style={{ width: 160 }} placeholder="CAM-DEMO-01" value={nc.camera_id} onChange={(e) => setNc({ ...nc, camera_id: e.target.value })} />
              <select className="input" style={{ width: 140 }} value={nc.place_type} onChange={(e) => setNc({ ...nc, place_type: e.target.value })}>{PLACE_TYPES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select>
              <input className="input" style={{ width: 110 }} placeholder="노선 30300037 (102번)" value={nc.route_id} onChange={(e) => setNc({ ...nc, route_id: e.target.value })} />
              <input className="input" style={{ width: 120 }} placeholder="정류장 30300037:42620" value={nc.stop_id} onChange={(e) => setNc({ ...nc, stop_id: e.target.value })} />
              <input className="input" style={{ width: 130 }} placeholder="차량 유형 VT_LOW" value={nc.vehicle_type_id} onChange={(e) => setNc({ ...nc, vehicle_type_id: e.target.value })} />
              <button className="btn btn-primary" onClick={registerCamera} disabled={!nc.camera_id}>등록</button>
            </div></details>
        </div>
        {cam && (
          <div className="row t-caption">
            <span>설치 장소: <b>{placeLabel(cam.place_type)}</b></span><span>소속 노선: <b>{cam.route_id ?? "—"}</b></span><span>차량 유형: <b>{cam.vehicle_type_id ?? "—"}</b></span>
            <span className={"status " + (cam.has_roi ? "status-free" : "status-crowded")}>ROI {cam.has_roi ? (cam.roi_stale ? "등록됨 · 검증 필요" : "등록됨") : `없음${c(" (G4)")}`}</span>
            <span className={"status " + (cam.has_capacity ? "status-free" : "status-crowded")}>정원 {cam.has_capacity ? `${cam.capacity ?? "등록"}명` : `미등록${c(" (G7)")}`}</span>
            <span className={"status " + (cam.has_mapping ? "status-free" : "status-none")}>매핑 {cam.has_mapping ? cam.vehicle_id : `없음${c(" (G10)")}`}</span>
          </div>
        )}
      </section>
      {msg && <div className="toast" role="status">{msg}</div>}
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
      {cam && (
        <>
          <div className="row" role="tablist" style={{ margin: "16px 0" }}>
            {([["roi", "ROI 2.2"], ["spec", "차량 제원 2.3"], ["map", "차량 번호 매핑 2.4"]] as [Tab, string][]).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={"chip" + (tab === k ? " selected" : "")} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          {tab === "roi" && (
            <div className="grid grid-2">
              <section className="utility-card stack"><h3 className="t-body-strong">2.2 관심영역 ROI</h3>
                <label className="field"><span className="t-caption">배경 프레임 (브라우저에만 표시, 서버 미전송)</span><input className="input" type="file" accept="image/*" onChange={(e) => { const f = e.target.files?.[0]; setBg(f ? URL.createObjectURL(f) : null); }} /></label>
                <PolygonEditor points={pts} onChange={setPts} imageUrl={bg} />
              </section>
              <section className="utility-card stack">
                <label className="field"><span className="t-caption">다각형 꼭짓점 (x,y)</span><textarea className="input" rows={3} value={pts.map((p) => p.join(",")).join(" ")} onChange={(e) => setPts(e.target.value.trim() ? e.target.value.trim().split(/\s+/).map((p) => p.split(",").map(Number)) : [])} /></label>
                <label className="field"><span className="t-caption">유효 시작일 (한국 시각)</span><input className="input" value={effFrom} onChange={(e) => setEffFrom(e.target.value)} /></label>
                <p className="t-caption muted">검증{c("(G8)")}: 꼭짓점 3개 이상, 변 교차 없음, 범위 내. 저장 시 이전 판본은 이력으로 남고 roi_stale 표시가 해제된다</p>
                <div className="row"><button className="btn btn-primary" onClick={saveRoi} disabled={pts.length < 3} title={pts.length < 3 ? `꼭짓점 3개 이상${c(" (G8)")}` : ""}>ROI 저장</button><button className="btn btn-secondary" onClick={() => setPts(FULL_FRAME_ROI)} title="사진·영상 전체에서 인원을 센다. 창밖·문 너머 사람도 셀 수 있다">전체 화면</button><button className="btn btn-pearl" onClick={() => setPts([])}>취소</button></div>
                <p className="t-caption muted">«전체 화면»: 사진·영상 전체에서 인원을 센다(혼잡 % = 인원 ÷ 정원). 창밖·문 너머 사람이 보이는 카메라는 그 부분을 뺀 ROI 가 더 정확하다</p>
                {rois[0] && <p className="t-caption muted">현재 판본 #{rois.find((r) => !r.superseded_at)?.roi_id ?? "—"}</p>}
              </section>
            </div>
          )}
          {tab === "spec" && (
            <section className="utility-card stack" style={{ maxWidth: 640 }}><h3 className="t-body-strong">2.3 차량 제원 (유형: {cam.vehicle_type_id ?? "미지정"})</h3>
              <div className="row"><label className="field"><span className="t-caption">차량 전체 정원 (혼잡 % = 인원 ÷ 정원, 카메라 합산)</span><input className="input" value={spec.capacity} onChange={(e) => setSpec({ ...spec, capacity: e.target.value })} /></label>
                <label className="field"><span className="t-caption">좌석 수</span><input className="input" value={spec.seat_count} onChange={(e) => setSpec({ ...spec, seat_count: e.target.value })} /></label></div>
              <label className="field"><span className="t-caption">출처 (필수{c(", BR-CV-16")})</span><input className="input" value={spec.source} onChange={(e) => setSpec({ ...spec, source: e.target.value })} /></label>
              <label className="field"><span className="t-caption">유효 시작일 (한국 시각)</span><input className="input" value={effFrom} onChange={(e) => setEffFrom(e.target.value)} /></label>
              <button className="btn btn-primary" onClick={saveSpec} disabled={!cam.vehicle_type_id || !spec.capacity || !spec.source} title={!cam.vehicle_type_id ? "카메라에 차량 유형이 없다" : ""}>제원 저장</button>
              {!cam.has_capacity && <p className="t-caption">이 유형의 카메라는 인원만 세고 혼잡도·잔여 인원은 '산출 불가' 상태다{c(" (G7)")}</p>}
            </section>
          )}
          {tab === "map" && (
            <section className="utility-card stack" style={{ maxWidth: 640 }}><h3 className="t-body-strong">2.4 카메라 ↔ 차량 번호 매핑</h3>
              <label className="field"><span className="t-caption">운행 정보 차량 목록 (자동완성) · 출처 {fleetStatus}</span>
                <input className="input" list="fleet" value={veh} onChange={(e) => setVeh(e.target.value)} placeholder="1234" /><datalist id="fleet">{fleet.map((v) => <option key={v.vehicle_id} value={v.vehicle_id} />)}</datalist></label>
              {fleetStatus !== "ok" && <GateBlock error={{ gate: "G12", reason_code: "FLEET_UNAVAILABLE", reason: `BIS 차량 목록을 조회할 수 없어 존재 검증 불가 — 저장은 '미검증' 상태로 허용된다${c(" (R11)")}`, resolver_role: "external", gate_event_id: null }} />}
              <p className="t-caption muted">현재 연결: <b>{myMap ? `${myMap.vehicle_id} (${myMap.verify_status}${myMap.verified_at ? " " + myMap.verified_at.slice(0, 10) : ""})` : "없음"}</b>{myMap?.sibling_cameras.length ? ` · 같은 차량의 다른 카메라: ${myMap.sibling_cameras.join(", ")}` : ""}</p>
              <div className="row"><button className="btn btn-primary" onClick={saveMap} disabled={!veh || !!myMap} title={myMap ? `이미 연결됨 — 해제 후 재등록${c(" (G9)")}` : ""}>매핑 저장</button>{myMap && <button className="btn btn-dark-utility" onClick={() => releaseMap(myMap.map_id)}>매핑 해제</button>}</div>
              {myMap && <p className="t-caption muted">해제 시 {myMap.vehicle_id} 의 기존 실측은 '실측 없음' 이 된다{c(" (UC12 A3)")}</p>}
            </section>
          )}
        </>
      )}
    </>
  );
}
