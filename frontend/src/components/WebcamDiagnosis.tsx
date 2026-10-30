/* 노트북 카메라 실시간 진단 (시연, T091) — 브라우저 카메라 화면을 간격(기본 1초)마다 1장 캡처해 /v1/web/diagnose 로 보낸다.
   영상 재생 실시간 진단과 같은 규칙: 요청 1건씩, 늦으면 그 칸은 건너뜀, 캡처는 긴 변 1920px 이하 JPEG, 장면은 저장하지 않는다(FR-11).
   - 카메라는 보안 연결(HTTPS)이나 localhost 에서만 켜진다 — http://192.168.0.19:9504 는 막히고 https://p4.sumzip.com 은 된다.
   - 끝이 없으므로 띠는 최근 WINDOW 칸만 흘려 보인다.
   - 정원은 카메라 차량 유형의 제원(UC7) — 운영 관리자는 여기서 바로 고칠 수 있다(새 제원 판본, S2 와 같은 API). */
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, post, type GateError } from "../api/client";
import { useAdmin, useCodes } from "../stores/auth";
import { configureWebcam, resumeWebcam, startWebcam, stopWebcam, useWebcam } from "../stores/webcam";
import type { CameraStatus } from "../api/types";
import { LEVEL_LABEL, LEVEL_VAR, LiveBadge, currentOf, heldSlot, stableSeries, type Slot, type Thresholds } from "./LiveVideoDiagnosis";

const WINDOW = 60;       // 띠에 보이는 최근 칸 수
const clock = (ms: number) => new Date(ms).toTimeString().slice(0, 8);

export function WebcamDiagnosis({ cameraId, camera, interval, enabled, thresholds, smoothWindow = 5, confirm = 2, onGate, onSelect, onCapacitySaved }: {
  cameraId: string; camera?: CameraStatus; interval: number; enabled: boolean; thresholds?: Thresholds | null;
  smoothWindow?: number; confirm?: number;
  onGate: (g: GateError) => void; onSelect: (s: Slot) => void; onCapacitySaved?: () => void;
}) {
  const codes = useCodes();   // 설계 번호는 운영 관리자에게만
  // 카메라·진단 루프는 stores/webcam 이 앱 전역에서 돌린다 — 이 화면을 떠나도(다른 메뉴·다른 탭) 꺼지지 않는다
  const videoRef = useRef<HTMLVideoElement>(null);
  const cam = useWebcam();
  const { stream, slots, cur, stopped, starting } = cam;
  const onGateRef = useRef(onGate); onGateRef.current = onGate;

  useEffect(() => { configureWebcam({ cameraId, interval, enabled }); }, [cameraId, interval, enabled]);
  useEffect(() => { if (videoRef.current) videoRef.current.srcObject = stream; }, [stream]);
  useEffect(() => { if (cam.stopGate) onGateRef.current(cam.stopGate); }, [cam.stopGate]);
  const camErr = cam.error;
  const start = () => { void startWebcam(); };
  const stop = stopWebcam;

  const series = useMemo(() => stableSeries(slots, smoothWindow, confirm, thresholds), [slots, smoothWindow, confirm, thresholds]);
  const heldOk = heldSlot(Object.fromEntries(Object.keys(series).map((k) => [k, slots[Number(k)]])), cur);
  const cu = heldOk != null ? currentOf(slots[heldOk].assessment!, thresholds) : null;
  const st = heldOk != null ? series[heldOk] : null;
  const last = heldSlot(slots, cur);
  const rej = last != null && slots[last].status === "rejected" ? slots[last] : null;
  const from = Math.max(0, cur - WINDOW + 1);
  const W = 1000, H = 28;

  return (
    <div className="stack">
      <div className="row">
        {!stream
          ? <button type="button" className="btn btn-primary" onClick={start} disabled={!cameraId || starting} title={cameraId ? "" : "카메라를 고른다"}>{starting ? "카메라 켜는 중… (권한 허용 필요)" : "카메라 켜기"}</button>
          : <button type="button" className="btn btn-secondary" onClick={stop}>카메라 끄기</button>}
        {stream && stopped && <button type="button" className="btn btn-pearl" onClick={resumeWebcam} title="게이트를 해제한 뒤(예: 카메라 전원 켜기) 진단을 다시 시작">진단 다시 시작</button>}
        <CapacityEditor camera={camera} onSaved={onCapacitySaved} />
      </div>
      {camErr && <p className="t-caption" style={{ color: "var(--status-crowded)" }}>{camErr}</p>}
      {stream && (
        <div style={{ position: "relative", lineHeight: 0 }}>
          <video ref={videoRef} className="preview" autoPlay muted playsInline style={{ width: "100%", maxHeight: 360, display: "block", transform: "scaleX(-1)" }} />
          {enabled && (
            <LiveBadge cu={cu} st={st} scene={heldOk != null ? `${clock(slots[heldOk].t)} 장면` : ""} smoothWindow={smoothWindow}
              rejected={rej ? `${clock(rej.t)} 장면 반려 — ${rej.reject?.reason ?? ""}` : null}
              idle={stopped ? `진단 중지 — ${stopped}` : "진단 준비 중…"} />
          )}
        </div>
      )}
      {stream && enabled && (
        <figure className="stack" style={{ margin: 0 }}>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img" aria-label={`최근 ${WINDOW}칸 혼잡 등급 띠`} style={{ display: "block", cursor: "pointer" }}
            onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              const i = from + Math.floor(((e.clientX - r.left) / r.width) * WINDOW);
              if (slots[i]) onSelect(slots[i]);
            }}>
            {Array.from({ length: WINDOW }, (_, k) => {
              const i = from + k, s = slots[i], c = s?.assessment ? currentOf(s.assessment, thresholds) : null;
              const fill = !s ? "var(--color-hairline)" : !c ? "var(--color-canvas)" : c.level ? LEVEL_VAR[c.level] : "var(--status-uncertain)";
              return <rect key={k} x={(k / WINDOW) * W} y={4} width={W / WINDOW - 1} height={H - 8} fill={fill} fillOpacity={c?.reference ? 0.4 : 1}
                stroke={s?.status === "rejected" ? "var(--status-crowded)" : "none"}><title>{s ? `${clock(s.t)} · ${c ? `${c.persons}${c.capacity ? `/${c.capacity}` : ""}명${c.occupied != null ? ` 혼잡 ${c.occupied.toFixed(0)}%` : ""} ${c.level ? LEVEL_LABEL[c.level] : ""}` : `반려 ${s.reject?.reason ?? ""}`}` : "미분석"}</title></rect>;
            })}
          </svg>
          <span className="t-caption muted">최근 {WINDOW}칸({Math.round(WINDOW * interval)}초) · {interval}초마다 1장 진단 · 칸을 누르면 결과 카드 · 장면은 저장하지 않는다{codes(" (FR-11)")}</span>
        </figure>
      )}
    </div>
  );
}

/** 정원 바로 고치기 — 운영 관리자 키가 있을 때만. 카메라 차량 유형의 새 제원 판본을 지금 시각으로 저장 (S2 «제원 저장»과 같은 API) */
function CapacityEditor({ camera, onSaved }: { camera?: CameraStatus; onSaved?: () => void }) {
  const [edit, setEdit] = useState(false);
  const [val, setVal] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const admin = useAdmin();   // T095: «관리자 로그인» 한 브라우저에서만 수정 버튼
  if (!camera) return null;
  const cap = camera.capacity;
  if (!admin || !camera.vehicle_type_id) return <span className="t-caption muted">정원 {cap != null ? `${cap}명` : "미등록"}</span>;
  const save = async () => {
    setMsg(null);
    try {
      await post(`/v1/admin/vehicle-types/${encodeURIComponent(camera.vehicle_type_id!)}/spec`, { admin: true,
        body: { capacity: Number(val), seat_count: null, source: "시연 조정 (노트북 카메라)", effective_from: new Date().toISOString().slice(0, 19) } });
      setEdit(false); setMsg(`정원 ${val}명으로 저장 — 다음 장면부터 적용`); onSaved?.();
    } catch (e) { setMsg(`저장 실패 — ${e instanceof ApiError && e.gate ? e.gate.reason : (e as Error).message}`); }
  };
  return (
    <span className="row" style={{ gap: 6 }}>
      {!edit ? (
        <>
          <span className="t-caption">정원 <b>{cap != null ? `${cap}명` : "미등록"}</b></span>
          <button type="button" className="btn btn-pearl" onClick={() => { setVal(String(cap ?? 25)); setEdit(true); setMsg(null); }}>정원 수정</button>
        </>
      ) : (
        <>
          <input className="input" style={{ width: 80 }} type="number" min={1} value={val} onChange={(e) => setVal(e.target.value)} aria-label="정원" />
          <button type="button" className="btn btn-primary" onClick={save} disabled={!(Number(val) >= 1)}>저장</button>
          <button type="button" className="btn btn-pearl" onClick={() => setEdit(false)}>취소</button>
        </>
      )}
      {msg && <span className="t-caption muted">{msg}</span>}
    </span>
  );
}
