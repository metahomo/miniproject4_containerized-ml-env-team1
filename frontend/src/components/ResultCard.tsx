/* C3 결과 카드 — 확정 / 판독 불확실 / 정원 없음 / (S7) 실측 없음. 원본 프레임은 두지 않는다 (U8).
   R22: 인원 ÷ 차량 전체 정원 — "30 / 45명 · 혼잡 67%" 를 크게, 여유 % 는 보조. 정원 초과는 100% 에서 멈추고 표시. */
import { useState } from "react";
import type { Assessment } from "../api/types";
import { fmtTime } from "../api/client";
import { SourceDrawer } from "./SourceDrawer";
import { StatusBadge, seatHint } from "./StatusBadge";
import { WarningChips } from "./WarningChips";
import { useCodes } from "../stores/auth";

/** "30 / 45명" · 혼잡 % 한 줄 — 결과 카드와 실시간 배지가 같은 문구를 쓴다 */
export function headcount(a: Pick<Assessment, "person_count" | "capacity" | "over_capacity" | "occupied_area_ratio" | "vacant_capacity_ratio">) {
  const hasCap = a.capacity != null && a.capacity > 0;
  return {
    persons: hasCap ? `${a.person_count} / ${a.capacity}명` : `${a.person_count}명`,
    crowd: hasCap ? `혼잡 ${a.occupied_area_ratio.toFixed(0)}%${a.over_capacity ? " · 정원 초과" : ""}` : "혼잡도 산출 불가 (정원 미등록)",
    vacant: hasCap ? `여유 ${a.vacant_capacity_ratio.toFixed(0)}%` : "",
  };
}

export function ResultCard({ a, demo, footer }: { a: Assessment; demo?: boolean; footer?: React.ReactNode }) {
  const c = useCodes();   // 설계 번호는 운영 관리자에게만
  const [open, setOpen] = useState(false);
  const ref = a.is_reference_only;
  const h = headcount(a);
  return (
    <section className="utility-card result stack" aria-label="진단 결과">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row" style={{ gap: 16 }}>
          <span className={"big" + (ref ? " ref" : "")} aria-label={ref ? "참고 인원" : "인원 / 정원"}>
            {ref ? "참고 " : ""}{h.persons}
          </span>
          <span className="stack" style={{ gap: 0 }}>
            <b>{h.crowd}</b>
            {h.vacant && <span className="t-caption muted">{h.vacant}</span>}
          </span>
          <StatusBadge level={a.crowding_level} suffix={ref ? "확정값 아님" : seatHint(a.crowding_level)} />
          {demo && <span className="badge">시연 모드</span>}
        </div>
        <button className="btn btn-pearl" onClick={() => setOpen(true)}>근거 보기</button>
      </div>
      <div className="meta t-caption">
        <span>잔여 인원 {a.remaining_not_computable ? <b className="status status-none">산출 불가</b> : `약 ${a.remaining_persons}명`}</span>
        <span>신뢰도 {a.mean_confidence.toFixed(2)}{ref && a.mean_confidence < 0.6 ? " (기준 0.6)" : ""}</span>
        <span>처리 {fmtTime(a.processed_at)}</span>
        {a.response_ms != null && <span>응답 {a.response_ms}ms</span>}
      </div>
      <div className="row"><span className="t-caption muted">경고</span><WarningChips warnings={a.warnings} onClick={() => setOpen(true)} /></div>
      {footer}
      <p className="notice">{a.notice}</p>
      {open && (
        <SourceDrawer onClose={() => setOpen(false)} title="근거">
          <dl>
            <dt>카메라</dt><dd>{a.camera_id}</dd>
            <dt>촬영 시각</dt><dd>{fmtTime(a.captured_at)}</dd>
            <dt>처리 시각</dt><dd>{fmtTime(a.processed_at)}</dd>
            <dt>ROI 판본</dt><dd>#{a.versions.roi_id}</dd>
            <dt>정원 판본</dt><dd>{a.versions.spec_id ? `#${a.versions.spec_id}${a.capacity ? ` (정원 ${a.capacity}명)` : ""}` : "없음 (산출 불가)"}</dd>
            <dt>계산</dt><dd>인원 세기 기준 이상 · 발 위치가 ROI 안인 사람 {a.person_count}명 ÷ 차량 전체 정원{c(" (R22)")}</dd>
            <dt>등급 기준</dt><dd>#{a.versions.threshold_policy_id}</dd>
            <dt>모델</dt><dd><code>{a.versions.model_commit}</code></dd>
            <dt>신뢰도</dt><dd>{a.mean_confidence.toFixed(3)} (기준 0.6)</dd>
            <dt>경고 사유</dt><dd>{a.warnings.length ? a.warnings.map((w, i) => <div key={i}><code>{w.code}</code> {w.detail}</div>) : "없음"}</dd>
          </dl>
        </SourceDrawer>
      )}
    </section>
  );
}
