/* S5 현재 프레임 진단 — 이용자 뷰 (UC1). 사진·영상을 /v1/web/* 가 규격에 맞춰 진단 경로로 넘긴다.
   사진: 제출 후 미리보기 제거, 결과 화면에 원본 없음 (U8). 영상: 재생하며 실시간 진단(칸별 등급 띠), 장면 1장 진단.
   (간격 진단 + 추이 그래프·평활값 표는 2026-09-30 삭제 — 실시간 진단과 겹치는 분석 도구. 관제 뷰의 ROI 검증 요청은 여기 G4 블록으로 옮김)
   영상 미리보기는 장면을 고르는 데 쓰는 이 브라우저 안의 파일이며 서버에 남지 않는다 (FR-11). */
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, get, post, type GateError, hhmm, kstInputToUtc } from "../api/client";
import { placeLabel } from "../api/place";
import type { Assessment, CameraStatus, GateEvent, Normalization, ThresholdPolicy, VideoResult, WebAssessment } from "../api/types";
import { GateBlock } from "../components/GateBlock";
import { LiveVideoDiagnosis, type Slot } from "../components/LiveVideoDiagnosis";
import { WebcamDiagnosis } from "../components/WebcamDiagnosis";
import { getWebcam } from "../stores/webcam";
import { ResultCard } from "../components/ResultCard";
import { useDemo } from "../stores/demo";
import { useReadiness } from "../stores/readiness";
import { SamplePicker } from "../components/SamplePicker";
import { useCodes, usePerms } from "../stores/auth";

type Kind = "image" | "video" | null;
const kindOf = (f: File | null): Kind => (!f ? null : f.type.startsWith("video/") || /\.(mp4|mov|avi|mkv|webm|m4v|ts|h26[45])$/i.test(f.name) ? "video" : "image");
const toGate = (err: unknown): GateError =>
  err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" };
const shift = (iso: string, sec: number) => {
  const d = new Date(iso.replace("Z", "") + "Z");
  return isNaN(d.getTime()) ? "" : new Date(d.getTime() + sec * 1000).toISOString().slice(0, 19);
};

function NormNote({ n }: { n?: Normalization | null }) {
  if (!n?.applied) return null;
  return <p className="t-caption muted">규격 변환 후 진단: {n.steps.join(" · ")} ({n.from.width}×{n.from.height} {n.from.format} → {n.to.width}×{n.to.height} {n.to.format})</p>;
}

export default function Diagnose() {
  const c = useCodes();   // 설계 번호는 운영 관리자에게만
  const [sp] = useSearchParams();
  const { ready } = useReadiness();
  const demo = useDemo();
  const cam0 = getWebcam();   // 노트북 카메라가 켜진 채 다른 화면에 다녀왔으면 그 카메라·간격·입력으로 돌아온다
  const [cameraId, setCameraId] = useState(sp.get("camera_id") ?? (cam0.stream ? cam0.cameraId : ""));
  const [cameras, setCameras] = useState<CameraStatus[]>([]);
  const [thr, setThr] = useState<{ free_min: number; crowded_max: number } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [meta, setMeta] = useState("");
  const [capturedAt, setCapturedAt] = useState("");
  const [intervalS, setIntervalS] = useState(cam0.stream ? String(cam0.interval) : "1");   // T089: 실시간 현재 인원은 1초마다 (검출 ~0.13초)
  const [live, setLive] = useState(true);
  const [source, setSource] = useState<"file" | "webcam">(cam0.stream ? "webcam" : "file");   // T091 입력: 파일 / 노트북 카메라
  const [sceneAt, setSceneAt] = useState("0");
  const [busy, setBusy] = useState<"" | "image" | "scene">("");
  const [delayed, setDelayed] = useState(false);
  const [result, setResult] = useState<WebAssessment | null>(null);
  const [resultLabel, setResultLabel] = useState("");
  const [gate, setGate] = useState<GateError | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [sample, setSample] = useState("");   // 고른 샘플 (catalog 의 file). 빈 값 = 로컬 파일
  const kind = kindOf(file);
  useEffect(() => { if (!file) setSample(""); }, [file]);   // 사진 제출 후 파일을 비우면 샘플 선택도 비운다
  // «버스 조회 S7» — 카메라 소속 노선(·정류장)을 넘긴다 (SD_01 P5 5.9 "필요 시 P7"). 노선·정류장이 다 있으면 S7 이 바로 조회한다
  const busLink = (camId: string) => {
    const c = cameras.find((x) => x.camera_id === camId);
    const q = new URLSearchParams();
    if (c?.route_id) q.set("route_id", c.route_id);
    if (c?.stop_id) q.set("stop_id", c.stop_id);
    return `/${q.toString() ? `?${q}` : ""}`;
  };
  const pickFile = (f: File | null) => { setFile(f); setResult(null); setGate(null); };

  // 이용자 조회 경로 — 관리자 키 없이도 카메라 목록·정원·등급 기준을 쓴다 (T095)
  const loadCameras = () => { get<CameraStatus[]>("/v1/reference/cameras").then(setCameras).catch(() => undefined); };
  useEffect(() => {
    loadCameras();
    get<Pick<ThresholdPolicy, "free_min_ratio" | "crowded_max_ratio">>("/v1/reference/threshold")
      .then((c) => setThr({ free_min: c.free_min_ratio, crowded_max: c.crowded_max_ratio }))
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    setPreviewFailed(false); setMeta("");
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    const size = `${(file.size / 1024 / 1024).toFixed(2)} MB · ${file.type || "형식 미상"}`;
    if (kindOf(file) === "image") {
      const im = new Image();
      im.onload = () => setMeta(`${im.naturalWidth}×${im.naturalHeight} · ${size}`);
      im.onerror = () => { setPreviewFailed(true); setMeta(size); };
      im.src = url;
    } else setMeta(size);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const begin = (b: typeof busy) => { setBusy(b); setGate(null); setResult(null); setResultLabel(""); };
  const end = () => { setBusy(""); setDelayed(false); };

  const submitImage = async () => {
    if (!file) return;
    begin("image");
    const fd = new FormData(); fd.append("camera_id", cameraId); fd.append("file", file);
    if (capturedAt) fd.append("captured_at", kstInputToUtc(capturedAt));
    try { setResult(await post<WebAssessment>("/v1/web/diagnose", { form: fd, onDelay: setDelayed })); setFile(null); }  // 제출 후 미리보기 제거 (FR-11)
    catch (err) { setGate(toGate(err)); } finally { end(); }
  };

  const liveInterval = Math.max(0.5, Number(intervalS) || 2);
  const pickSlot = (s: Slot) => {
    setResult(s.assessment ?? null); setResultLabel(`실시간 · ${s.t.toFixed(1)}초 장면`);
    setGate(s.status === "rejected" && s.reject ? s.reject : null);
  };

  /* 장면 1장: 브라우저가 재생할 수 있으면 지금 화면을 잘라 사진으로, 못 하면 시각(초)을 서버에 보내 서버가 뽑는다 */
  const submitScene = async () => {
    if (!file) return;
    begin("scene");
    const el = videoRef.current;
    try {
      if (el && !previewFailed && el.videoWidth > 0) {
        const t = el.currentTime;
        const c = document.createElement("canvas"); c.width = el.videoWidth; c.height = el.videoHeight;
        c.getContext("2d")?.drawImage(el, 0, 0);
        const blob = await new Promise<Blob | null>((res) => c.toBlob(res, "image/jpeg", 0.92));
        if (!blob) throw new Error("장면을 이미지로 만들지 못했다");
        const fd = new FormData(); fd.append("camera_id", cameraId); fd.append("file", blob, "scene.jpg");
        if (capturedAt) fd.append("captured_at", shift(kstInputToUtc(capturedAt), t));
        setResult(await post<WebAssessment>("/v1/web/diagnose", { form: fd, onDelay: setDelayed })); setResultLabel(`장면 ${t.toFixed(1)}초`);
      } else {
        const fd = new FormData(); fd.append("camera_id", cameraId); fd.append("file", file); fd.append("at_s", sceneAt);
        if (capturedAt) fd.append("started_at", kstInputToUtc(capturedAt));
        const v = await post<VideoResult>("/v1/web/diagnose-video", { form: fd });
        const it = v.items[0];
        if (it?.assessment) { setResult(it.assessment); setResultLabel(`장면 ${it.t.toFixed(1)}초`); }
        else setGate(toGate(new ApiError(422, it?.reject?.reason ?? "반려", it?.reject as GateError)));
      }
    } catch (err) { setGate(toGate(err)); } finally { end(); }
  };

  const onSubmit = (e: React.FormEvent) => { e.preventDefault(); if (kind === "image") submitImage(); else if (kind === "video") submitScene(); };
  const disabled = !ready || !!busy || !file || !cameraId;
  const reason = !ready ? `준비 중 — 진단 API 서버 준비 완료 후 요청${c(" (G0)")}` : !file ? "샘플을 고르거나 사진·영상 파일을 선택한다" : !cameraId ? "카메라를 고른다" : "";
  const busyText = (what: string) => (delayed ? "지연 중… (2초 초과)" : what);
  // ROI 검증 요청 (관제 뷰에서 옮김) — ROI 가 위치·각도 변경 뒤 미갱신인 카메라면 G4 블록. 게이트 이벤트는 관제 권한이 있어야 읽혀 요청 버튼이 켜진다
  const canReadEvents = usePerms().includes("control_view");
  const roiStale = !!result && !!cameras.find((x) => x.camera_id === result.camera_id)?.roi_stale;
  const [g4, setG4] = useState<number | null>(null);
  useEffect(() => {
    setG4(null);
    if (!roiStale || !canReadEvents || !result) return;
    get<GateEvent[]>("/v1/admin/gate-events", { admin: true, query: { subject_kind: "camera", subject_id: result.camera_id } })
      .then((ev) => setG4(ev.find((e) => e.gate_code === "G4")?.event_id ?? null)).catch(() => undefined);
  }, [roiStale, canReadEvents, result?.camera_id]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="page-title">
        <h1 className="t-display-md">현재 프레임 진단</h1>
        <p className="t-caption">사진 1장 또는 영상 → 잔여 탑승 가능 비율(%)·등급·경고. 큰 사진·다른 형식(HEIC·WebP 등)·영상은 규격(JPEG, 긴 변 1920px 이하)으로 바꿔 진단한다. 짧은 변 240px 미만은 키우지 않고 반려한다</p>
      </div>
      <div className="grid grid-2">
        <form className="utility-card stack" onSubmit={onSubmit} aria-label="5.2 프레임 제출">
          <h3 className="t-body-strong">5.2 사진 · 영상 제출</h3>
          <label className="field"><span className="t-caption">카메라</span>
            {cameras.length ? (
              <select className="input" value={cameraId} onChange={(e) => setCameraId(e.target.value)} required>
                <option value="">선택</option>
                {cameras.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {placeLabel(c.place_type)}{c.has_roi ? "" : " · ROI 없음"}</option>)}
              </select>
            ) : <input className="input" value={cameraId} onChange={(e) => setCameraId(e.target.value)} placeholder="CAM-DEMO-01" required />}
          </label>
          <div className="row" role="radiogroup" aria-label="입력">
            <label className="chip"><input type="radio" checked={source === "file"} onChange={() => setSource("file")} /> 사진 · 영상 파일</label>
            <label className="chip"><input type="radio" checked={source === "webcam"} onChange={() => { setSource("webcam"); pickFile(null); }} /> 노트북 카메라 (실시간)</label>
          </div>
          {source === "webcam" && (
            <div className="stack">
              <label className="field" style={{ width: 120 }}><span className="t-caption">진단 간격 (초)</span>
                <input className="input" type="number" min={0.5} step={0.5} value={intervalS} onChange={(e) => setIntervalS(e.target.value)} /></label>
              <WebcamDiagnosis cameraId={cameraId} camera={cameras.find((c) => c.camera_id === cameraId)} interval={liveInterval} enabled={ready} thresholds={thr}
                onGate={setGate} onSelect={(s) => { pickSlot(s); setResultLabel(`노트북 카메라 · ${hhmm(new Date(s.t).toISOString(), true)} 장면`); }} onCapacitySaved={loadCameras} />
              <p className="t-caption muted">시연용: 카메라는 https://p4.sumzip.com(또는 localhost)에서만 켜진다. 혼잡 % = 현재 인원 ÷ 선택한 카메라의 정원</p>
            </div>
          )}
          {source === "file" && (<>
          <SamplePicker value={sample} onPick={(name, f) => { setSample(name); if (fileInput.current) fileInput.current.value = ""; pickFile(f); }} />
          <label className="field"><span className="t-caption">사진 또는 영상{sample ? " (샘플 사용 중 — 파일을 고르면 샘플 대신 쓴다)" : ""}</span>
            <input ref={fileInput} className="input" type="file" accept="image/*,video/*,.heic,.heif,.avi,.mkv,.ts" onChange={(e) => { setSample(""); pickFile(e.target.files?.[0] ?? null); }} required={!file} />
          </label>
          <label className="field"><span className="t-caption">{kind === "video" ? "영상 시작 시각 (선택, 한국 시각 — 프레임마다 더해 촬영 시각으로 쓴다)" : "촬영 시각 (선택, 한국 시각)"}</span>
            <input className="input" value={capturedAt} onChange={(e) => setCapturedAt(e.target.value)} placeholder="2026-09-28T09:41:07" />
          </label>

          {kind === "image" && preview && (
            <div className="stack">
              {!previewFailed && <img className="preview" src={preview} alt="제출 전 미리보기" />}
              <span className="t-caption muted">{meta}{previewFailed ? " · 이 브라우저가 미리 보여 줄 수 없는 형식 — 서버에서 변환한다" : ""} · 제출 후 미리보기는 사라지고 결과 화면에 원본은 남지 않는다{c(" (FR-11)")}</span>
            </div>
          )}

          {kind === "video" && preview && (
            <div className="stack">
              {!previewFailed
                ? <LiveVideoDiagnosis src={preview} videoRef={videoRef} cameraId={cameraId} interval={liveInterval} capturedAt={capturedAt ? kstInputToUtc(capturedAt) : ""} enabled={live && ready} thresholds={thr}
                    onGate={setGate} onSelect={pickSlot} onError={() => setPreviewFailed(true)} />
                : <p className="t-caption muted">이 브라우저가 재생할 수 없는 코덱이다 — 진단은 서버가 영상을 읽어 한다</p>}
              <span className="t-caption muted">{meta} · 원본 영상은 서버에 저장되지 않는다{c(" (FR-11)")}</span>
              <div className="row">
                {!previewFailed && (
                  <label className="row t-caption" style={{ gap: 6 }}>
                    <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} />재생하며 실시간 진단
                  </label>
                )}
                <label className="field" style={{ width: 120 }}><span className="t-caption">진단 간격 (초)</span>
                  <input className="input" type="number" min={0.5} step={0.5} value={intervalS} onChange={(e) => setIntervalS(e.target.value)} /></label>
                {previewFailed && (
                  <label className="field" style={{ width: 120 }}><span className="t-caption">장면 시각 (초)</span>
                    <input className="input" type="number" min={0} step={0.1} value={sceneAt} onChange={(e) => setSceneAt(e.target.value)} /></label>
                )}
              </div>
              {live && !previewFailed && <span className="t-caption muted">실시간: 재생 위치가 간격 칸에 들어설 때마다 그 장면 1장을 진단한다(검출이 늦으면 그 칸은 건너뜀)</span>}
            </div>
          )}

          <div className="row">
            {kind !== "video" ? (
              <button className="btn btn-primary" type="submit" disabled={disabled} aria-disabled={disabled} title={reason}>
                {busy === "image" ? busyText("진단 중…") : "진단 요청"}
              </button>
            ) : (
              <button className="btn btn-primary" type="submit" disabled={disabled} aria-disabled={disabled} title={reason}>
                {busy === "scene" ? busyText("진단 중…") : previewFailed ? `${sceneAt}초 장면 진단` : "지금 장면 진단"}
              </button>
            )}
            {!ready && <span className="t-caption muted">사유: 준비 중{c(" (G0)")}</span>}
          </div>
          </>)}
        </form>

        <div className="stack">
          {result && (
            <>
              {resultLabel && <p className="t-caption muted">{resultLabel}</p>}
              <ResultCard a={result as Assessment} demo={demo.on} footer={<div className="stack"><NormNote n={result.normalization} /><div className="row"><Link className="btn btn-secondary" to={busLink(result.camera_id)}>버스 조회{c(" S7")}</Link></div></div>} />
            </>
          )}
          {roiStale && result && (
            <GateBlock error={{ gate: "G4", reason_code: "ROI_STALE", reason: `이 카메라의 ROI 는 위치·각도 변경 뒤 갱신되지 않았다 — 결과에 경고가 함께 붙는다${c(" (P0 0.6)")}`, resolver_role: "operator", gate_event_id: g4 }} />
          )}
          {gate && <GateBlock error={gate} onRetry={() => setGate(null)} retryLabel="요청 수정" />}
          {!result && !gate && <section className="utility-card"><p className="muted t-caption">결과가 여기에 표시된다. 영상은 재생하며 장면마다 진단하고, 판독 불확실이면 "참고" 수치와 경고가 표시된다.</p></section>}
        </div>
      </div>
    </>
  );
}
