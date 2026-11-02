/* C8 경고 칩 목록 — 코드 + 한글 사유 */
import type { Warning } from "../api/types";

export const WARN_KO: Record<string, string> = {
  blur: "영상 흐림", low_light: "저조도", backlight: "역광", low_confidence: "신뢰도 낮음", occlusion: "승객 겹침",
  roi_stale: "ROI 검증 필요", partial_coverage: "카메라 일부 누락", unknown: "판독 불가 사유",
};

export function WarningChips({ warnings, onClick }: { warnings: Warning[]; onClick?: (w: Warning) => void }) {
  if (!warnings?.length) return <span className="muted t-caption">경고 없음</span>;
  return (
    <span className="row" style={{ gap: 6 }}>
      {warnings.map((w, i) => (
        <button key={i} type="button" className="chip" style={{ padding: "4px 10px", fontSize: 13 }} title={w.detail ?? ""} onClick={() => onClick?.(w)}>
          <code style={{ background: "transparent", padding: 0 }}>{w.code}</code> {WARN_KO[w.code] ?? ""}
        </button>
      ))}
    </span>
  );
}
