/* C4 상태 배지 — 색 + 글자 (색만으로 전달하지 않는다) */
const LABEL: Record<string, string> = {
  free: "여유", normal: "보통", crowded: "혼잡", uncertain: "판독 불확실", none: "실측 없음", no_measurement: "실측 없음",
  unavailable: "조회 불가", not_computable: "산출 불가",
};
const CLS: Record<string, string> = { free: "status-free", normal: "status-normal", crowded: "status-crowded", uncertain: "status-uncertain" };

export function StatusBadge({ level, suffix }: { level?: string | null; suffix?: string }) {
  const key = level ?? "none";
  const cls = CLS[key] ?? "status-none";
  const label = LABEL[key] ?? key;
  const aria = key === "uncertain" ? "판독 불확실 — 확정값 아님" : `혼잡 등급 ${label}`;
  return (
    <span className={"status " + cls} aria-label={aria}>
      {label}{suffix ? ` · ${suffix}` : ""}
    </span>
  );
}

export const seatHint = (level?: string | null) => (level === "free" ? "착석 가능" : level === "crowded" ? "앉을 자리 없음" : level === "normal" ? "입석 여유" : "");
