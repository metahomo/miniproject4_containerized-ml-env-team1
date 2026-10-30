/* S2b 카메라 전원 관리 — 등록된 카메라 전원을 한 화면에서 켜고 끈다 (2026-09-29 사용자 요청).
   - off(기본): 그 카메라의 진단 요청을 서버가 거부한다 (G4 CAMERA_POWER_OFF, 409).
   - on: 서버가 카메라마다 «진단 주기»(초)마다 «프레임 소스»(스냅샷 URL 또는 샘플 영상)에서 1장을 불러와 진단한다.
   - 표는 엑셀처럼 칸이 나뉜 시트: [지하철] 호선·차량번호·칸·상태·정원·현재 인원·밀집도·동작여부·on/off, [버스] 호선·칸 없이 같다.
   - 5초마다 새로 읽는다. 수치는 최근 진단의 통계적 추정치. 밀집도 = 현재 인원 ÷ 정원 (R22). */
import { Fragment, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, get, hhmm, kst, patch, post, type GateError } from "../../api/client";
import type { CameraPowerRow, SampleMedia } from "../../api/types";
import { GateBlock } from "../../components/GateBlock";
import { useCodes } from "../../stores/auth";

const REFRESH_MS = 5000;
const RUN: Record<string, string> = { running: "운행중", stopped: "정차" };
const OP: Record<string, { label: string; color: string }> = {
  normal: { label: "정상 작동", color: "var(--status-free)" },
  offline: { label: "오프라인", color: "var(--status-crowded)" },
  off: { label: "꺼짐", color: "var(--status-uncertain)" },
};
// «102번 · 간선 · 수통골기점지↔대전역 (30300037)» → «102번» (표 칸이 좁다 — 2026-09-30 노선 이름에 유형·기점↔반환점이 붙음)
const routeShort = (r: CameraPowerRow) => { const n = (r.route_name ?? r.route_id ?? "—").replace(/\s*\(.*\)\s*$/, ""); return n.match(/^\S+?번/)?.[0] ?? n; };

export default function Cameras() {
  const c = useCodes();   // 설계 번호는 운영 관리자에게만 (2026-09-30)
  const [rows, setRows] = useState<CameraPowerRow[] | null>(null);
  const [samples, setSamples] = useState<SampleMedia[]>([]);
  const [gate, setGate] = useState<GateError | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [at, setAt] = useState<number>(0);

  const load = useCallback(async () => {
    try {
      setRows(await get<CameraPowerRow[]>("/v1/admin/camera-power", { admin: true }));
      setAt(Date.now());
    } catch (e) { if (e instanceof ApiError && e.gate) setGate(e.gate); }
  }, []);
  useEffect(() => {
    load();
    get<SampleMedia[]>("/v1/web/samples").then(setSamples).catch(() => setSamples([]));
    const id = window.setInterval(load, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [load]);

  const replace = (row: CameraPowerRow) => setRows((rs) => rs?.map((r) => (r.camera_id === row.camera_id ? row : r)) ?? rs);
  const fail = (e: unknown) => setGate(e instanceof ApiError && e.gate ? e.gate : { gate: "—", reason_code: "ERROR", reason: (e as Error).message, resolver_role: "self" });

  const toggle = async (r: CameraPowerRow) => {
    setGate(null); setMsg(null); setPending(r.camera_id);
    try {
      const row = await post<CameraPowerRow>(`/v1/admin/cameras/${encodeURIComponent(r.camera_id)}/power`, { admin: true, body: { on: !r.powered } });
      replace(row);
      setMsg(row.powered
        ? `${r.camera_id} 켬 — ${row.frame_source ? `${row.poll_interval_s}초마다 자동 진단` : "진단 요청을 받는다 (프레임 소스가 없어 자동 진단은 하지 않는다 — ⚙ 설정)"}`
        : `${r.camera_id} 끔 — 진단 요청을 거부한다`);
    } catch (e) { fail(e); } finally { setPending(null); }
  };

  const saveSettings = async (id: string, body: Record<string, unknown>) => {
    setGate(null); setMsg(null);
    try {
      replace(await patch<CameraPowerRow>(`/v1/admin/cameras/${encodeURIComponent(id)}/operation`, { admin: true, body }));
      setMsg(`${id} 설정 저장`); setOpen(null);
    } catch (e) { fail(e); }
  };

  const rail = rows?.filter((r) => r.mode === "rail") ?? [];
  const bus = rows?.filter((r) => r.mode === "bus") ?? [];
  const onCount = rows?.filter((r) => r.powered).length ?? 0;

  const common = (r: CameraPowerRow) => (
    <>
      <td>{r.run_state ? RUN[r.run_state] : <span className="muted" title="차량 매핑 없음">—</span>}</td>
      <td className="num">{r.capacity ?? "—"}</td>
      <td className="num" title={r.last_diagnosed_at ? `최근 진단 ${kst(r.last_diagnosed_at)}` : "진단 기록 없음"}>{r.persons ?? "—"}</td>
      <td className="num">{r.density != null ? `${r.density.toFixed(1)}%` : "—"}</td>
      <td>
        <span className="status" style={{ color: OP[r.operation].color }} title={r.last_diagnosed_at ? `최근 진단 ${hhmm(r.last_diagnosed_at, true)}` : "진단 기록 없음"}>● {OP[r.operation].label}</span>
        {r.last_error && <div className="t-caption" style={{ color: "var(--status-crowded)" }} title={r.last_error}>자동 진단 실패 — {r.last_error.slice(0, 40)}</div>}
      </td>
      <td>
        <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
          <button type="button" role="switch" aria-checked={r.powered} aria-label={`${r.camera_id} 전원`} className={"power" + (r.powered ? " on" : "")}
            disabled={pending === r.camera_id} onClick={() => toggle(r)}>
            <span className="knob" />{r.powered ? "ON" : "OFF"}
          </button>
          <button type="button" className="btn btn-pearl sheet-gear" title="칸 · 프레임 소스 · 진단 주기" aria-expanded={open === r.camera_id}
            onClick={() => setOpen((o) => (o === r.camera_id ? null : r.camera_id))}>⚙</button>
        </span>
      </td>
    </>
  );
  const vehicleCell = (r: CameraPowerRow, withRoute: boolean) => (
    <td>
      <b>{withRoute ? `${routeShort(r)}${r.vehicle_id ? ` · ${r.vehicle_id}` : ""}` : r.vehicle_id ?? "—"}</b>
      <div className="t-caption muted">{r.camera_id}</div>
    </td>
  );
  const editor = (r: CameraPowerRow, cols: number) => open === r.camera_id && (
    <tr className="sheet-edit"><td colSpan={cols}><SettingsForm row={r} samples={samples} onSave={(b) => saveSettings(r.camera_id, b)} onCancel={() => setOpen(null)} /></td></tr>
  );

  return (
    <>
      <div className="page-title">
        <h1 className="t-display-md">카메라 전원 관리</h1>
        <p className="t-caption">등록된 카메라의 진단 기능을 켜고 끈다. <b>꺼짐(기본)</b>이면 진단 요청을 거부하고, <b>켜면</b> 정해 둔 주기마다 프레임 소스에서 장면을 불러와 자동 진단한다. 밀집도 = 현재 인원 ÷ 정원 (통계적 추정치)</p>
      </div>
      {msg && <div className="toast" role="status">{msg}</div>}
      {gate && <GateBlock error={gate} />}
      <div className="row" style={{ justifyContent: "space-between", marginBottom: "var(--space-sm)" }}>
        <span className="t-caption muted">카메라 {rows?.length ?? 0}대 · 켜짐 {onCount}대 · {REFRESH_MS / 1000}초마다 갱신{at ? ` (마지막 ${new Date(at).toTimeString().slice(0, 8)})` : ""}</span>
        <span className="row" style={{ gap: 8 }}>
          <Link className="t-caption" to="/admin/onboarding">카메라 등록 · 매핑 →</Link>
          <button type="button" className="btn btn-pearl" onClick={load}>새로고침</button>
        </span>
      </div>

      <section className="stack" aria-label="지하철">
        <h2 className="t-tagline">[ 지하철 ]</h2>
        <div className="sheet-wrap">
          <table className="sheet">
            <thead><tr><th>호선</th><th>차량번호</th><th>위치하는 칸</th><th>상태</th><th>정원</th><th>현재 인원</th><th>밀집도(%)</th><th>동작여부</th><th>on/off</th></tr></thead>
            <tbody>
              {rail.map((r) => (
                <Fragment key={r.camera_id}>
                  <tr className={r.powered ? "" : "is-off"}>
                    <td>{routeShort(r)}</td>
                    {vehicleCell(r, false)}
                    <td>{r.car_position ? `${r.car_position}칸` : <span className="muted">—</span>}</td>
                    {common(r)}
                  </tr>
                  {editor(r, 9)}
                </Fragment>
              ))}
              {rows && !rail.length && <tr><td colSpan={9} className="muted">등록된 지하철(열차 차내) 카메라가 없다 — «카메라 · 차량 투입 등록»에서 설치 장소를 «열차 차내»로 등록한다</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="stack" aria-label="버스" style={{ marginTop: "var(--space-xl)" }}>
        <h2 className="t-tagline">[ 버스 ]</h2>
        <div className="sheet-wrap">
          <table className="sheet">
            <thead><tr><th>차량번호</th><th>상태</th><th>정원</th><th>현재 인원</th><th>밀집도(%)</th><th>동작여부</th><th>on/off</th></tr></thead>
            <tbody>
              {bus.map((r) => (
                <Fragment key={r.camera_id}>
                  <tr className={r.powered ? "" : "is-off"}>
                    {vehicleCell(r, true)}
                    {common(r)}
                  </tr>
                  {editor(r, 7)}
                </Fragment>
              ))}
              {rows && !bus.length && <tr><td colSpan={7} className="muted">등록된 버스 카메라가 없다</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      <p className="t-caption muted" style={{ marginTop: "var(--space-md)" }}>
        상태: 연결된 차량이 최근 10분 BIS 도착 정보에 있으면 운행중, 없으면 정차. 동작여부: 켜져 있고 최근 5분 안에 진단 기록이 있으면 정상 작동, 없으면 오프라인.
        노트북 카메라{c("(S5)")}로 진단할 때도 그 카메라가 켜져 있어야 한다.
      </p>
    </>
  );
}

function SettingsForm({ row, samples, onSave, onCancel }: { row: CameraPowerRow; samples: SampleMedia[]; onSave: (b: Record<string, unknown>) => void; onCancel: () => void }) {
  const isSample = !!row.frame_source?.startsWith("sample:");
  const [kind, setKind] = useState<"none" | "sample" | "url">(!row.frame_source ? "none" : isSample ? "sample" : "url");
  const [sample, setSample] = useState(isSample ? row.frame_source!.slice(7) : samples[0]?.file ?? "");
  const [url, setUrl] = useState(!isSample ? row.frame_source ?? "" : "");
  const [interval, setInterval_] = useState(String(row.poll_interval_s));
  const [car, setCar] = useState(row.car_position ? String(row.car_position) : "");
  const source = kind === "none" ? "" : kind === "sample" ? `sample:${sample}` : url.trim();
  const ok = Number(interval) >= 1 && (kind !== "url" || /^https?:\/\//.test(url.trim())) && (kind !== "sample" || !!sample) && (!car || Number(car) >= 1);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { frame_source: source, poll_interval_s: Number(interval) };
    if (row.mode === "rail" && car) body.car_position = Number(car);
    onSave(body);
  };
  return (
    <form className="row" style={{ gap: "var(--space-md)", alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={submit} aria-label={`${row.camera_id} 운영 설정`}>
      {row.mode === "rail" && (
        <label className="field" style={{ width: 110 }}><span className="t-caption">위치하는 칸</span>
          <input className="input" type="number" min={1} value={car} onChange={(e) => setCar(e.target.value)} placeholder="예: 2" /></label>
      )}
      <label className="field"><span className="t-caption">프레임 소스</span>
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
          <option value="none">없음 (요청만 받음 — 노트북 카메라 등)</option>
          <option value="sample">서버 샘플 영상 (시연)</option>
          <option value="url">스냅샷 URL (IP 카메라)</option>
        </select></label>
      {kind === "sample" && (
        <label className="field"><span className="t-caption">샘플</span>
          <select className="input" value={sample} onChange={(e) => setSample(e.target.value)}>
            {samples.map((s) => <option key={s.file} value={s.file}>{s.title}</option>)}
          </select></label>
      )}
      {kind === "url" && (
        <label className="field" style={{ minWidth: 280, flex: 1 }}><span className="t-caption">스냅샷 URL (JPEG·PNG 1장을 돌려주는 주소)</span>
          <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://192.168.0.50/snapshot.jpg" /></label>
      )}
      <label className="field" style={{ width: 120 }}><span className="t-caption">진단 주기 (초)</span>
        <input className="input" type="number" min={1} step={1} value={interval} onChange={(e) => setInterval_(e.target.value)} /></label>
      <button type="submit" className="btn btn-primary" disabled={!ok}>저장</button>
      <button type="button" className="btn btn-pearl" onClick={onCancel}>취소</button>
    </form>
  );
}
