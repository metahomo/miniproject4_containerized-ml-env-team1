/* 노트북 카메라 세션 스토어 — 카메라 스트림과 1초 진단 루프를 화면(컴포넌트) 밖 앱 전역에 둔다.
   예전에는 WebcamDiagnosis 가 사라지면(사이드바의 다른 메뉴, «사진·영상 파일» 탭) 카메라를 껐다. 이제는 «카메라 끄기»를 누를 때만 끈다.
   - 캡처용 <video> 는 화면과 별개로 여기서 만든다(DOM 밖) — 화면의 미리보기는 같은 스트림을 따로 붙인다.
   - 타이머는 Web Worker 에서 돈다 — 브라우저 탭을 바꿔도 메인 스레드 타이머 지연(백그라운드 스로틀)에 걸리지 않는다.
   - 규칙은 전과 같다: 요청 1건씩, 늦으면 그 칸은 건너뜀, 캡처는 긴 변 1920px 이하 JPEG, 장면은 저장하지 않는다(FR-11). */
import { useEffect, useState } from "react";
import { ApiError, post, type GateError } from "../api/client";
import type { WebAssessment } from "../api/types";
import { ABORT_GATES, capture, type Slot } from "../components/LiveVideoDiagnosis";

const KEEP = 300;   // 메모리에 두는 칸 수

export interface WebcamState {
  stream: MediaStream | null;
  cameraId: string;
  interval: number;
  enabled: boolean;
  slots: Record<number, Slot>;
  t0: number;
  cur: number;
  stopped: string | null;      // 진단 중지 사유 (ABORT_GATES·서버 무응답)
  stopGate: GateError | null;
  starting: boolean;
  error: string | null;        // 카메라 켜기 실패 사유
}

let st: WebcamState = { stream: null, cameraId: "", interval: 1, enabled: false, slots: {}, t0: 0, cur: 0, stopped: null, stopGate: null, starting: false, error: null };
const listeners = new Set<(s: WebcamState) => void>();
let video: HTMLVideoElement | null = null;
let worker: Worker | null = null;
let fallbackTimer: number | undefined;
let busy = false;
let tried = new Set<number>();

function set(patch: Partial<WebcamState>) {
  st = { ...st, ...patch };
  listeners.forEach((l) => l(st));
}

export const getWebcam = () => st;

function resetSlots() {
  tried = new Set(); busy = false;
  set({ slots: {}, t0: Date.now(), cur: 0, stopped: null, stopGate: null });
}

/** 화면이 고른 카메라·간격·준비 상태를 알린다. 카메라나 간격이 바뀌면 띠를 새로 시작 */
export function configureWebcam(c: { cameraId: string; interval: number; enabled: boolean }) {
  const changed = c.cameraId !== st.cameraId || c.interval !== st.interval;
  set({ cameraId: c.cameraId, interval: c.interval, enabled: c.enabled });
  if (changed) resetSlots();
}

async function diagnose(el: HTMLVideoElement, slot: number) {
  busy = true; tried.add(slot);
  const at = Date.now();
  const cameraId = st.cameraId;
  try {
    const { blob } = await capture(el);
    const fd = new FormData(); fd.append("camera_id", cameraId); fd.append("file", blob, "webcam.jpg");
    fd.append("captured_at", new Date(at).toISOString().slice(0, 19));
    const a = await post<WebAssessment>("/v1/web/diagnose", { form: fd });
    if (cameraId !== st.cameraId) return;   // 도중에 카메라를 바꿨다 — 버린다
    const next: Record<number, Slot> = { ...st.slots, [slot]: { t: at, status: "accepted", assessment: a } };
    for (const k of Object.keys(next)) if (Number(k) < slot - KEEP) delete next[Number(k)];
    set({ slots: next });
  } catch (err) {
    const g: GateError = err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" };
    if (ABORT_GATES.has(g.gate) || (err instanceof ApiError && err.offline)) set({ stopped: g.reason, stopGate: g });
    else set({ slots: { ...st.slots, [slot]: { t: at, status: "rejected", reject: g } } });
  } finally {
    busy = false;
  }
}

function tick() {
  if (!st.stream || !video) return;
  const slot = Math.floor((Date.now() - st.t0) / 1000 / st.interval);
  if (slot !== st.cur) set({ cur: slot });
  if (st.enabled && !st.stopped && st.cameraId && !busy && video.readyState >= 2 && video.videoWidth > 0 && !tried.has(slot)) void diagnose(video, slot);
}

function startTimer() {
  try {
    // Worker 안의 타이머는 탭이 백그라운드여도 1초 미만 간격을 지킨다
    const src = "let id; onmessage = (e) => { clearInterval(id); if (e.data === 'start') id = setInterval(() => postMessage(0), 100); };";
    worker = new Worker(URL.createObjectURL(new Blob([src], { type: "text/javascript" })));
    worker.onmessage = tick;
    worker.postMessage("start");
  } catch {
    fallbackTimer = window.setInterval(tick, 100);
  }
}

function stopTimer() {
  worker?.postMessage("stop"); worker?.terminate(); worker = null;
  if (fallbackTimer) window.clearInterval(fallbackTimer);
  fallbackTimer = undefined;
}

export async function startWebcam() {
  set({ error: null, stopped: null, stopGate: null });
  if (st.stream) return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    set({ error: "이 주소에서는 브라우저가 카메라를 막는다 — https://p4.sumzip.com 또는 localhost 로 접속한다" });
    return;
  }
  set({ starting: true });
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    video = document.createElement("video");
    video.muted = true; video.playsInline = true; video.srcObject = stream;
    await video.play().catch(() => undefined);
    stream.getVideoTracks().forEach((t) => t.addEventListener("ended", stopWebcam));   // 브라우저 쪽에서 카메라를 끊었을 때
    set({ stream });
    resetSlots();
    startTimer();
  } catch (e) {
    set({ error: `카메라를 켜지 못했다 — ${(e as Error).name === "NotAllowedError" ? "권한이 거부됐다(주소창의 카메라 권한 확인)" : (e as Error).message}` });
  } finally {
    set({ starting: false });
  }
}

export function stopWebcam() {
  stopTimer();
  st.stream?.getTracks().forEach((t) => t.stop());
  if (video) { video.pause(); video.srcObject = null; }
  video = null; busy = false;
  set({ stream: null });
}

/** 멈춘 진단을 다시 시작 (게이트 해제 후 — 예: 카메라 전원을 켠 뒤) */
export function resumeWebcam() {
  set({ stopped: null, stopGate: null });
  tried = new Set();
}

export function useWebcam(): WebcamState {
  const [s, setS] = useState(st);
  useEffect(() => {
    listeners.add(setS);
    setS(st);
    return () => { listeners.delete(setS); };
  }, []);
  return s;
}
