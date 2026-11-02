/* S6 후속 차량 실측 등록 (UC10) — 차량 식별자·차내 카메라·프레임 → 실측 등록 상태. G10 블록 + 요청 보내기. */
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, fmtTime, get, post, type GateError, kstInputToUtc } from "../api/client";
import { isInVehicle, placeLabel } from "../api/place";
import type { CameraStatus, MeasurementResult } from "../api/types";
import { GateBlock } from "../components/GateBlock";
import { ResultCard } from "../components/ResultCard";
import { StatusBadge } from "../components/StatusBadge";
import { useCodes } from "../stores/auth";
import { useReadiness } from "../stores/readiness";

export default function Measurement() {
  const c = useCodes();   // 설계 번호는 운영 관리자에게만 (2026-09-30)
  const { ready } = useReadiness();
  const [sp] = useSearchParams();
  // 차량 번호는 고른 카메라에 연결된 차량으로 채운다 — 한 카메라는 한 차량에만 속한다 (2026-09-30 — 이전: 기본값 "1234" 가 남아
  // S8 에서 실제 102번 차량으로 다시 연결한 카메라에 등록하면 G10 MAPPING_MISSING 으로 거부됐다)
  const [vehicleId, setVehicleId] = useState("");
  const [cameraId, setCameraId] = useState(sp.get("camera_id") ?? "");
  const [cameras, setCameras] = useState<CameraStatus[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [capturedAt, setCapturedAt] = useState("");
  const [res, setRes] = useState<MeasurementResult | null>(null);
  const [gate, setGate] = useState<GateError | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { get<CameraStatus[]>("/v1/reference/cameras")   /* 이용자 조회 (T095) */.then((cs) => setCameras(cs.filter((c) => isInVehicle(c.place_type)))).catch(() => undefined); }, []);
  const mappedVehicle = cameras.find((x) => x.camera_id === cameraId)?.vehicle_id ?? "";
  useEffect(() => { setVehicleId(mappedVehicle); }, [cameraId, mappedVehicle]);   // 카메라를 바꾸거나 목록이 오면 연결 차량으로

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); if (!file) return;
    setBusy(true); setGate(null); setRes(null);
    const fd = new FormData(); fd.append("vehicle_id", vehicleId); fd.append("camera_id", cameraId); fd.append("file", file); if (capturedAt) fd.append("captured_at", kstInputToUtc(capturedAt));
    try { setRes(await post<MeasurementResult>("/v1/web/measurements", { form: fd })); setFile(null); }
    catch (err) { setGate(err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" }); }
    finally { setBusy(false); }
  };
  const m = res?.measurement;
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">후속 차량 실측 등록</h1><p className="t-caption">차량 식별자가 지정된 차내 프레임을 진단해 카메라 최신 실측으로 보관하고 차량 단위로 합산한다. 판독 불확실도 실측으로 보관된다{c(" (BR-CV-23)")}</p></div>
      <div className="grid grid-2">
        <form className="utility-card stack" onSubmit={submit} aria-label="6.1 제출">
          <h3 className="t-body-strong">6.1 제출</h3>
          <label className="field"><span className="t-caption">카메라 (차내 유형만)</span>
            {cameras.length ? <select className="input" value={cameraId} onChange={(e) => setCameraId(e.target.value)} required><option value="">선택</option>{cameras.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {placeLabel(c.place_type)}{c.has_mapping ? ` · ${c.vehicle_id}` : " · 매핑 없음"}</option>)}</select>
              : <input className="input" value={cameraId} onChange={(e) => setCameraId(e.target.value)} placeholder="CAM-DEMO-01" required />}
          </label>
          <label className="field"><span className="t-caption">차량 식별자 (버스 차량 번호 / 열차 편성 번호{c(" — UC12 표기")}) — 카메라에 연결된 차량이 채워진다</span><input className="input" value={vehicleId} onChange={(e) => setVehicleId(e.target.value)} required /></label>
          {cameraId && cameras.length > 0 && !mappedVehicle && <p className="t-caption" style={{ color: "var(--status-crowded)" }}>이 카메라에 연결된 차량이 없다 — 투입 등록(또는 시연 준비 «운행 차량 연결»)에서 먼저 연결한다</p>}
          {mappedVehicle && vehicleId !== mappedVehicle && <p className="t-caption" style={{ color: "var(--status-crowded)" }}>이 카메라는 {mappedVehicle} 에 연결돼 있다 — 다른 번호로는 등록되지 않는다</p>}
          <label className="field"><span className="t-caption">차내 프레임 (큰 사진·HEIC 등은 규격으로 변환)</span><input className="input" type="file" accept="image/*,.heic,.heif" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required /></label>
          <label className="field"><span className="t-caption">촬영 시각 (선택, 한국 시각)</span><input className="input" value={capturedAt} onChange={(e) => setCapturedAt(e.target.value)} placeholder="2026-09-28T09:38:20" /></label>
          <button className="btn btn-primary" disabled={!ready || busy || !file || !cameraId} title={!ready ? `준비 중${c(" (G0)")}` : ""}>{busy ? "등록 중…" : "실측 등록"}</button>
        </form>
        <div className="stack">
          {res && m && (
            <>
              <ResultCard a={res.assessment} demo={m.demo_mode} />
              <section className="utility-card stack" aria-label="6.6 실측 등록 상태">
                <h3 className="t-body-strong">차량 {m.vehicle_id}호 합산 실측</h3>
                <div className="row" style={{ gap: 16 }}><span className="result big">{m.capacity ? `${m.persons_sum ?? "—"} / ${m.capacity}명` : `여유 ${m.vacant_ratio_agg.toFixed(0)}%`}</span>{m.capacity != null && <span className="stack" style={{ gap: 0 }}><b>혼잡 {(100 - m.vacant_ratio_agg).toFixed(0)}%{(m.persons_sum ?? 0) > m.capacity ? " · 정원 초과" : ""}</b><span className="t-caption muted">여유 {m.vacant_ratio_agg.toFixed(0)}% · 카메라 합산</span></span>}<StatusBadge level={m.crowding_level_agg} /><span className="chip">커버리지 {m.coverage_num}/{m.coverage_den}{m.partial_coverage ? " · partial_coverage" : ""}</span>{m.demo_mode && <span className="badge">시연 모드</span>}</div>
                <div className="meta t-caption"><span>실측 시각 {fmtTime(m.measured_at)}</span><span>유효 만료 {fmtTime(m.expires_at)} (유효 시간 {m.applied_validity_minutes}분)</span>{m.already_expired && <b className="status status-none">촬영 시각이 이미 만료 — 즉시 실측 없음 취급</b>}</div>
                {res.assessment.crowding_level === "uncertain" && <p className="t-caption">등급 판독 불확실·경고가 그대로 실측으로 보관되었다. 즉시 재촬영·재제출을 권한다.</p>}
                <div className="row"><Link className="btn btn-secondary" to="/">버스 조회{c(" S7")}</Link><button className="btn btn-pearl" onClick={() => setRes(null)}>같은 차량 재제출</button></div>
              </section>
            </>
          )}
          {gate && <GateBlock error={gate} onRetry={() => setGate(null)} />}
        </div>
      </div>
    </>
  );
}
