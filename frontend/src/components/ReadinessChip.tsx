/* C5 준비 상태 표시 — ready / preparing / unavailable + 재확인. 검출기 적재 시간을 툴팁으로 (모델 로딩 시간 노출 — 운영 관리자에게만). */
import { usePerms } from "../stores/auth";
import { useReadiness } from "../stores/readiness";

const LABEL = { ready: "진단 가능", preparing: "준비 중", unavailable: "진단 불가" } as const;

export function ReadinessChip() {
  const { readiness, offline, refresh } = useReadiness();
  const state = offline ? "unavailable" : readiness?.readiness ?? "preparing";
  const admin = usePerms().includes("admin");   // 검출기 기술 정보는 운영 관리자에게만 (2026-09-30)
  const d = admin ? readiness?.detector : undefined;
  const tip = offline
    ? "진단 API 서버에 연결할 수 없다"
    : d
      ? `${d.kind} ${d.model} · 적재 ${d.load_seconds ?? "?"}s · 최근 추론 ${d.last_infer_ms ?? "?"}ms${d.note ? " · " + d.note : ""}`
      : "";
  const cls = state === "ready" ? "status-free" : state === "preparing" ? "status-normal" : "status-crowded";
  return (
    <button className={"chip"} onClick={() => refresh()} title={(tip ? tip + " " : "") + "(클릭: 재확인)"} aria-label={`준비 상태 ${LABEL[state]}, 클릭하면 재확인`}>
      <span className={"status " + cls}>{LABEL[state]}</span>
    </button>
  );
}
