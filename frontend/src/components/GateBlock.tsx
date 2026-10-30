/* C2 차단 블록 — 사유 · 해제 주체 · 다음 행동. 사라지지 않는다 (U1). 타인 해제면 RequestButton (U5). */
import type { GateError } from "../api/client";
import { useCodes } from "../stores/auth";
import { RequestButton } from "./RequestButton";

const ROLE: Record<string, string> = { self: "본인 (값 수정 후 재시도)", operator: "운영 관리자", external: "외부 기관 복구 후 재시도", undefined: "미정 (절차 확정 필요)" };
const GATE_SCREEN: Record<string, string> = { G3: "S2 투입 등록", G4: "S2 투입 등록 · ROI", G7: "S2 투입 등록 · 제원", G10: "S2 투입 등록 · 매핑", G0: "S1 서버 준비", G5: "S1 서버 준비" };

/** plain — 게이트 번호·사유 코드·화면 번호를 숨긴다. 주지 않으면 설계 번호 표시 규칙(useCodes)을 따른다 (2026-09-30) */
export function GateBlock({ error, onRetry, retryLabel = "수정 후 재시도", extra, plain: plainProp }: { error: GateError; onRetry?: () => void; retryLabel?: string; extra?: React.ReactNode; plain?: boolean }) {
  const c = useCodes();
  const plain = plainProp ?? !c("x");
  const output = ["G6", "G7", "G12", "G13"].includes(error.gate);
  return (
    <section className={"gate" + (output ? " output" : "")} role="alert" aria-live="polite">
      <h4>{output ? "출력 차단" : "차단 상태"}{plain ? "" : ` · ${error.gate} ${error.reason_code}`}</h4>
      <dl className="kv">
        <dt>사유</dt><dd>{error.reason}</dd>
        <dt>해제 주체</dt><dd>{ROLE[error.resolver_role] ?? error.resolver_role}{!plain && GATE_SCREEN[error.gate] && error.resolver_role === "operator" ? ` — ${GATE_SCREEN[error.gate]}` : ""}</dd>
        {error.allowed_spec && (
          <>
            <dt>허용 규격</dt>
            <dd><code>{JSON.stringify(error.allowed_spec)}</code></dd>
          </>
        )}
        {error.details?.length ? (
          <>
            <dt>항목</dt>
            <dd>{error.details.map((d, i) => <div key={i}>{String(d.field ?? "")} — {String(d.reason ?? "")}</div>)}</dd>
          </>
        ) : null}
      </dl>
      <div className="row">
        {error.resolver_role === "self" && onRetry && <button className="btn btn-secondary" onClick={onRetry}>{retryLabel}</button>}
        {error.resolver_role !== "self" && <RequestButton eventId={error.gate_event_id ?? null} gate={error.gate} plain={plain} />}
        {extra}
      </div>
    </section>
  );
}
