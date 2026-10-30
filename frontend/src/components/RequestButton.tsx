/* C7 요청 보내기 — 해제 주체가 운영 관리자인 게이트에서만. 전송 후 "요청 보냄 (시각)" 으로 바뀌고 게이트는 그대로 닫혀 있다. */
import { useState } from "react";
import { ApiError, post, hhmm } from "../api/client";
import type { GateEvent } from "../api/types";

export function RequestButton({ eventId, gate, label = "운영 관리자에게 요청 보내기", plain = false }: { eventId: number | null; gate: string; label?: string; plain?: boolean }) {
  const [sent, setSent] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (sent) return <span className="chip" aria-live="polite">요청 보냄 · {hhmm(sent, true)}{plain ? "" : ` (${gate})`}</span>;
  const disabled = !eventId || busy;
  const reason = !eventId ? "이 게이트는 이벤트가 기록되지 않아 요청을 보낼 수 없다" : busy ? "전송 중" : "";
  return (
    <span className="row">
      <button
        className="btn btn-dark-utility" aria-disabled={disabled} disabled={disabled} title={reason || label}
        onClick={async () => {
          if (!eventId) return;
          setBusy(true);
          try {
            const ev = await post<GateEvent>(`/v1/gate-events/${eventId}/request`);
            setSent(ev.request_sent_at ?? new Date().toISOString());
          } catch (e) {
            setErr(e instanceof ApiError ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {label}
      </button>
      {disabled && reason && <span className="t-caption muted">{reason}</span>}
      {err && <span className="t-caption" style={{ color: "var(--status-crowded)" }}>{err}</span>}
    </span>
  );
}
