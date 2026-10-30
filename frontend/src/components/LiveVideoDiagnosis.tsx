/* 재생하며 실시간 진단 — 영상은 브라우저에서 그대로 재생하고, 재생 위치가 간격(초) 칸에 들어설 때마다 그 장면 1장을
   /v1/web/diagnose 로 보낸다(기존 사진 진단 경로 그대로 — 요청마다 DB 에 메타가 남는다).
   - 요청은 항상 1건만. 검출이 간격보다 느리면 그 칸은 건너뛴다(띠에 빈칸). 되감으면 받아 둔 칸 결과를 다시 쓴다.
   - 캡처는 긴 변 1920px 이하 JPEG 로 만든다 → 웹 백엔드가 다시 줄이지 않으므로 ROI 좌표가 캡처 좌표와 같다.
   - 캡처한 장면은 요청 동안만 메모리에 있고 저장하지 않는다 (FR-11).
   - 큰 숫자는 현재 인원(방금 분석한 장면, 간격마다 갱신 — T089). 혼잡 % = 현재 인원 ÷ 차량 전체 정원(R22).
     보조로 안정 인원: 최근 window 칸 인원 중앙값이 같은 방향으로 confirm 칸 연속 달라질 때만 바뀐다(흔들림 확인용).
     판독 불확실 장면은 "참고"로 표시 (FR-09). */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, get, post, type GateError } from "../api/client";
import type { Assessment, Roi, WebAssessment } from "../api/types";

export const CAPTURE_MAX_SIDE = 1920;   // backend NORMALIZE_MAX_SIDE 와 같게
export const ABORT_GATES = new Set(["G0", "G1", "G3", "G4", "G5"]);   // 이 게이트면 다음 칸도 같은 결과 — 멈춘다 (routers/web_media.py 와 같음)
export const LEVEL_LABEL: Record<string, string> = { free: "여유", normal: "보통", crowded: "혼잡", uncertain: "판독 불확실" };
export const LEVEL_VAR: Record<string, string> = { free: "var(--status-free)", normal: "var(--status-normal)", crowded: "var(--status-crowded)", uncertain: "var(--status-uncertain)" };

export interface Slot { t: number; status: "accepted" | "rejected"; assessment?: Assessment; reject?: GateError }

export const slotOf = (t: number, interval: number) => Math.max(0, Math.floor(t / interval + 1e-6));
export const slotCount = (duration: number, interval: number) => Math.max(1, Math.ceil(duration / interval - 1e-6));

/** 현재 칸까지 받은 결과 중 가장 최근 칸 (칸 사이에는 직전 값을 유지) */
export function heldSlot(slots: Record<number, Slot>, cur: number): number | null {
  let best: number | null = null;
  for (const k of Object.keys(slots)) { const i = Number(k); if (i <= cur && (best == null || i > best)) best = i; }
  return best;
}

export interface Stable {
  persons: number;            // 안정 인원 (정수)
  raw: number;                // 이번 장면 인원
  capacity: number | null;    // 차량 전체 정원 (R22)
  occupied: number | null;    // 혼잡 % = 안정 인원 ÷ 정원 (100 상한)
  vacant: number | null;      // 여유 %
  over: boolean;              // 정원 초과
  level: string | null;
  reference: boolean;
}
export interface Thresholds { free_min: number; crowded_max: number }

/** 서버 map_level 과 같은 규칙 (predict.py) */
export const levelOf = (v: number, thr: Thresholds) => (v >= thr.free_min ? "free" : v <= thr.crowded_max ? "crowded" : "normal");

export interface Current { persons: number; capacity: number | null; occupied: number | null; vacant: number | null; over: boolean; level: string | null; reference: boolean }

/** 장면 1장의 현재 인원·혼잡 — 서버 값 그대로. 등급은 서버 등급, 판독 불확실이면 기준값으로 값의 등급을 매기고 "참고" */
export function currentOf(a: Assessment, thr?: Thresholds | null): Current {
  const cap = a.capacity && a.capacity > 0 ? a.capacity : null;
  const occupied = cap ? a.occupied_area_ratio : null;
  const vacant = cap ? a.vacant_capacity_ratio : null;
  const unsure = a.crowding_level === "uncertain";
  const level = vacant == null ? null : !unsure ? a.crowding_level : thr ? levelOf(vacant, thr) : null;
  return { persons: a.person_count, capacity: cap, occupied, vacant, over: !!a.over_capacity, level, reference: cap != null && unsure };
}

/** 칸별 안정 인원 (R22). 받아들여진 칸만 칸 순서대로 훑는다 — 되감아도 같은 칸이면 같은 값.
    최근 window 칸 인원의 중앙값이 같은 방향으로 confirm 칸 연속 달라질 때만 표시 인원을 바꾼다 → 사람이 그대로면 숫자도 그대로. */
export function stableSeries(slots: Record<number, Slot>, window = 5, confirm = 2, thr?: Thresholds | null): Record<number, Stable> {
  const idx = Object.keys(slots).map(Number).filter((i) => slots[i].status === "accepted").sort((a, b) => a - b);
  const out: Record<number, Stable> = {};
  let shown: number | null = null, pending = 0, dir = 0;
  idx.forEach((i, k) => {
    const win = idx.slice(Math.max(0, k - window + 1), k + 1).map((j) => slots[j].assessment!);
    const vals = win.map((x) => x.person_count).sort((a, b) => a - b), m = vals.length >> 1;
    const med = Math.round(vals.length % 2 ? vals[m] : (vals[m - 1] + vals[m]) / 2);
    if (shown == null) shown = med;
    else if (med !== shown) {
      const d = Math.sign(med - shown);
      pending = d === dir ? pending + 1 : 1; dir = d;
      if (pending >= confirm) { shown = med; pending = 0; dir = 0; }
    } else { pending = 0; dir = 0; }
    const a = slots[i].assessment!;
    const cap = a.capacity && a.capacity > 0 ? a.capacity : null;
    const occupied = cap ? Math.min(100, (shown / cap) * 100) : null;
    const vacant = occupied != null ? 100 - occupied : null;
    // 판독 불확실 칸 중 정원 없음(산출 불가)은 품질 문제가 아니므로 "참고" 판정에서 뺀다
    const sure = win.filter((x) => x.crowding_level !== "uncertain");
    const level = vacant == null ? null : thr ? levelOf(vacant, thr) : sure.length ? sure[sure.length - 1].crowding_level : null;
    out[i] = { persons: shown, raw: a.person_count, capacity: cap, occupied, vacant, over: cap != null && shown > cap, level,
               reference: cap != null && sure.length * 2 < win.length };
  });
  return out;
}

export async function capture(el: HTMLVideoElement): Promise<{ blob: Blob; w: number; h: number }> {
  const r = Math.min(1, CAPTURE_MAX_SIDE / Math.max(el.videoWidth, el.videoHeight));
  const w = Math.round(el.videoWidth * r), h = Math.round(el.videoHeight * r);
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  c.getContext("2d")?.drawImage(el, 0, 0, w, h);
  const blob = await new Promise<Blob | null>((res) => c.toBlob(res, "image/jpeg", 0.9));
  if (!blob) throw new Error("장면을 이미지로 만들지 못했다");
  return { blob, w, h };
}

/** 영상 위 배지 — 현재 인원 / 정원 · 혼잡 % · 여유 % + 안정 인원. 영상 재생·웹캠이 같이 쓴다 */
export function LiveBadge({ cu, st, scene, smoothWindow, rejected, idle }: {
  cu: Current | null; st: Stable | null; scene: string; smoothWindow: number; rejected?: string | null; idle: string;
}) {
  const color = cu?.level && !cu.reference ? LEVEL_VAR[cu.level] : "var(--status-uncertain)";
  return (
    <div role="status" aria-live="polite" style={{ position: "absolute", top: 10, left: 10, lineHeight: 1.2, background: "var(--color-canvas)",
      borderRadius: 10, borderLeft: `6px solid ${color}`, padding: "8px 12px", boxShadow: "var(--shadow-product)", minWidth: 150 }}>
      {cu && st ? (
        <>
          <div className="t-caption" style={{ color, fontWeight: 700 }}>현재 인원 · {cu.level ? LEVEL_LABEL[cu.level] : cu.capacity ? "판독 불확실" : "혼잡도 산출 불가 (정원 미등록)"}{cu.reference ? " · 참고" : ""}</div>
          <div style={{ fontSize: 30, fontWeight: 700 }}>{cu.persons}{cu.capacity ? <span style={{ fontSize: 18 }}> / {cu.capacity}명</span> : <span style={{ fontSize: 18 }}>명</span>}</div>
          {cu.occupied != null && <div className="t-body-strong">혼잡 {cu.occupied.toFixed(0)}%{cu.over ? " · 정원 초과" : ""} <span className="t-caption muted" style={{ fontWeight: 400 }}>여유 {cu.vacant!.toFixed(0)}%</span></div>}
          <div className="t-caption muted">{scene} · 안정 {st.persons}명 (최근 {smoothWindow}칸)</div>
        </>
      ) : rejected ? (
        <div className="t-caption">{rejected}</div>
      ) : (
        <div className="t-caption muted">{idle}</div>
      )}
    </div>
  );
}

export function LiveVideoDiagnosis({ src, videoRef, cameraId, interval, capturedAt, enabled, smoothWindow = 5, confirm = 2, thresholds, onGate, onSelect, onError }: {
  src: string; videoRef: React.RefObject<HTMLVideoElement>; cameraId: string; interval: number; capturedAt?: string;
  enabled: boolean; smoothWindow?: number; confirm?: number; thresholds?: Thresholds | null;
  onGate: (g: GateError) => void;                         // 멈춰야 하는 차단 (준비·인증·카메라·ROI·모델)
  onSelect: (s: Slot) => void;                            // 띠의 칸을 눌렀을 때 → 결과 카드
  onError: () => void;                                    // 브라우저가 재생할 수 없는 코덱
}) {
  const [slots, setSlots] = useState<Record<number, Slot>>({});
  const [now, setNow] = useState(0);
  const [duration, setDuration] = useState(0);
  const [frame, setFrame] = useState<{ w: number; h: number } | null>(null);
  const [inflight, setInflight] = useState(false);
  const [stopped, setStopped] = useState<string | null>(null);
  const [roi, setRoi] = useState<number[][] | null>(null);
  const busy = useRef(false);
  const tried = useRef<Set<number>>(new Set());
  const epoch = useRef(0);
  const slotsRef = useRef(slots); slotsRef.current = slots;
  const onGateRef = useRef(onGate); onGateRef.current = onGate;

  // 파일·카메라·간격이 바뀌면 받아 둔 칸을 버린다 (늦게 온 응답도 epoch 로 버림)
  useEffect(() => { epoch.current++; setSlots({}); tried.current = new Set(); setStopped(null); busy.current = false; setInflight(false); }, [src, cameraId, interval]);

  useEffect(() => {
    setRoi(null);
    if (!cameraId) return;
    get<Roi>(`/v1/reference/cameras/${encodeURIComponent(cameraId)}/roi`)   // 이용자 조회 (T095)
      .then((r) => setRoi(r.polygon ?? null)).catch(() => undefined);
  }, [cameraId]);

  const diagnose = useCallback(async (el: HTMLVideoElement, slot: number) => {
    busy.current = true; setInflight(true); tried.current.add(slot);
    const my = epoch.current, t = el.currentTime;
    try {
      const { blob } = await capture(el);
      const fd = new FormData(); fd.append("camera_id", cameraId); fd.append("file", blob, "live.jpg");
      if (capturedAt) { const d = new Date(capturedAt.replace("Z", "") + "Z"); if (!isNaN(d.getTime())) fd.append("captured_at", new Date(d.getTime() + t * 1000).toISOString().slice(0, 19)); }
      const a = await post<WebAssessment>("/v1/web/diagnose", { form: fd });
      if (my === epoch.current) setSlots((s) => ({ ...s, [slot]: { t, status: "accepted", assessment: a } }));
    } catch (err) {
      if (my !== epoch.current) return;
      const g: GateError = err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" };
      if (ABORT_GATES.has(g.gate) || (err instanceof ApiError && err.offline)) { setStopped(g.reason); onGateRef.current(g); el.pause(); }
      else setSlots((s) => ({ ...s, [slot]: { t, status: "rejected", reject: g } }));
    } finally {
      if (my === epoch.current) { busy.current = false; setInflight(false); }
    }
  }, [cameraId, capturedAt]);

  // 재생 위치를 따라가며, 비어 있는 현재 칸을 1건씩 진단한다 (일시정지·이동 후에도 그 칸 1장)
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const el = videoRef.current;
      if (el) {
        setNow(Math.round(el.currentTime * 10) / 10);
        if (el.duration && isFinite(el.duration)) setDuration(el.duration);
        const last = el.duration && isFinite(el.duration) ? slotCount(el.duration, interval) - 1 : Infinity;
        const slot = Math.min(slotOf(el.currentTime, interval), last);   // 끝 위치(= 길이)는 마지막 칸
        if (enabled && !stopped && cameraId && !busy.current && el.readyState >= 2 && el.videoWidth > 0 && !el.seeking
            && !tried.current.has(slot) && !(slot in slotsRef.current)) void diagnose(el, slot);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, interval, enabled, stopped, cameraId, diagnose]);

  const n = slotCount(duration, interval);
  const cur = Math.min(slotOf(now, interval), n - 1);
  const held = heldSlot(slots, cur);
  const hs = held != null ? slots[held] : null;
  const series = useMemo(() => stableSeries(slots, smoothWindow, confirm, thresholds), [slots, smoothWindow, confirm, thresholds]);
  const heldOk = heldSlot(Object.fromEntries(Object.keys(series).map((k) => [k, slots[Number(k)]])), cur);
  const st = heldOk != null ? series[heldOk] : null;
  const done = Object.keys(slots).length;
  const missed = Array.from({ length: Math.min(cur, n) }, (_, i) => i).filter((i) => !(i in slots) && tried.current.has(i) === false).length;
  const cu = heldOk != null ? currentOf(slots[heldOk].assessment!, thresholds) : null;
  const W = 1000, H = 28;

  return (
    <div className="stack">
      <div style={{ position: "relative", lineHeight: 0 }}>
        <video ref={videoRef} className="preview" src={src} controls muted playsInline onError={onError}
          onLoadedMetadata={(e) => { const v = e.currentTarget, r = Math.min(1, CAPTURE_MAX_SIDE / Math.max(v.videoWidth, v.videoHeight)); setFrame({ w: Math.round(v.videoWidth * r), h: Math.round(v.videoHeight * r) }); }}
          style={{ width: "100%", maxHeight: 360, display: "block" }} />
        {roi && frame && (
          <svg viewBox={`0 0 ${frame.w} ${frame.h}`} preserveAspectRatio="xMidYMid meet" aria-hidden
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
            <polygon points={roi.map((p) => p.join(",")).join(" ")} fill="none" stroke="var(--color-primary)" strokeWidth={Math.max(2, frame.w / 400)} strokeDasharray="12 8" />
          </svg>
        )}
        {enabled && (
          <LiveBadge cu={cu} st={st} scene={heldOk != null ? `${slots[heldOk].t.toFixed(1)}초 장면` : ""} smoothWindow={smoothWindow}
            rejected={hs?.status === "rejected" ? `${hs.t.toFixed(1)}초 장면 반려 — ${hs.reject?.reason ?? ""}` : null}
            idle={stopped ? "진단 중지" : inflight ? "진단 중…" : "재생하면 진단을 시작한다"} />
        )}
      </div>

      {enabled && duration > 0 && (
        <figure className="stack" style={{ margin: 0 }}>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img" aria-label={`${interval}초 칸별 혼잡 등급 띠`} style={{ display: "block", cursor: "pointer" }}
            onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              const i = Math.min(n - 1, Math.floor(((e.clientX - r.left) / r.width) * n));
              const el = videoRef.current; if (el) el.currentTime = Math.min(i * interval, Math.max(0, duration - 0.05));
              if (slots[i]) onSelect(slots[i]);
            }}>
            {Array.from({ length: n }, (_, i) => {
              const s = slots[i], v = series[i], c = s?.assessment ? currentOf(s.assessment, thresholds) : null;
              const fill = !s ? "var(--color-hairline)" : s.status === "rejected" || !c ? "var(--color-canvas)" : c.level ? LEVEL_VAR[c.level] : "var(--status-uncertain)";
              return <rect key={i} x={(i / n) * W} y={4} width={W / n - (n < 200 ? 1 : 0)} height={H - 8} fill={fill} fillOpacity={c?.reference ? 0.4 : 1}
                stroke={s?.status === "rejected" ? "var(--status-crowded)" : "none"}><title>{`${(i * interval).toFixed(1)}초 · ${s ? (c && v ? `현재 ${c.persons}${c.capacity ? `/${c.capacity}` : ""}명${c.occupied != null ? ` 혼잡 ${c.occupied.toFixed(0)}%` : ""} ${c.level ? LEVEL_LABEL[c.level] : ""}${c.reference ? " (참고)" : ""} · 안정 ${v.persons}명` : `반려 ${s.reject?.reason ?? ""}`) : "미분석"}`}</title></rect>;
            })}
            <line x1={(now / duration) * W} x2={(now / duration) * W} y1={0} y2={H} stroke="var(--color-ink)" strokeWidth={3} vectorEffect="non-scaling-stroke" />
          </svg>
          <div className="row t-caption muted" aria-label="범례">
            {(["free", "normal", "crowded"] as const).map((k) => (
              <span key={k} className="row" style={{ gap: 4 }}><svg width="10" height="10" aria-hidden><rect width="10" height="10" fill={LEVEL_VAR[k]} /></svg>{LEVEL_LABEL[k]}</span>
            ))}
            <span className="row" style={{ gap: 4 }}><svg width="10" height="10" aria-hidden><rect width="10" height="10" fill="var(--status-normal)" fillOpacity={0.4} /></svg>흐리게 = 참고(판독 불확실 장면)</span>
            <span className="row" style={{ gap: 4 }}><svg width="10" height="10" aria-hidden><rect width="10" height="10" fill="var(--color-hairline)" /></svg>미분석</span>
            <span>· {interval}초 칸 {done}/{n} 분석{missed ? ` · 건너뜀 ${missed}` : ""} · 칸을 누르면 그 시점으로 이동</span>
          </div>
        </figure>
      )}
    </div>
  );
}
