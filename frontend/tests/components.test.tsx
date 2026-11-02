/* T071 — 컴포넌트 게이트 표현: GateBlock(사유·해제 주체·요청 버튼 조건), ResultCard(4변형·참고 접두) */
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { login, logout } from "../src/stores/auth";
import { GateBlock } from "../src/components/GateBlock";
import { ResultCard } from "../src/components/ResultCard";
import type { Assessment } from "../src/api/types";

const base: Assessment = {
  assessment_id: 1, camera_id: "CAM-B12", occupied_area_ratio: 38, vacant_capacity_ratio: 62, crowding_level: "free", is_reference_only: false,
  person_count: 30, capacity: 80, over_capacity: false, remaining_persons: 48, remaining_not_computable: false, mean_confidence: 0.81, warnings: [], notice: "이 수치는 통계적 추정치입니다",
  processed_at: "2026-09-28T09:41:08", response_ms: 900, versions: { roi_id: 1, spec_id: 1, threshold_policy_id: 1, model_commit: "abc" },
};

afterEach(() => { act(() => logout()); vi.unstubAllGlobals(); });
/** 관리자 키로 로그인 — 서버가 admin 으로 확인하고 모든 권한을 돌려준다 */
async function asAdmin() {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ role: "admin", permissions: ["admin"] }) }) as unknown as Response));
  await act(async () => { await login("k"); });
}

describe("GateBlock", () => {
  it("타인 해제 게이트는 요청 버튼, 본인 해제는 재시도 버튼", () => {
    render(<GateBlock error={{ gate: "G4", reason_code: "ROI_MISSING", reason: "ROI 없음", resolver_role: "operator", gate_event_id: 7 }} />);
    expect(screen.getByText("차단 상태")).toBeTruthy();          // 이용자에게는 게이트 번호·사유 코드를 숨긴다
    expect(screen.queryByText(/G4/)).toBeNull();
    expect(screen.getByText("운영 관리자에게 요청 보내기")).toBeTruthy();
    render(<GateBlock error={{ gate: "G8", reason_code: "X", reason: "값 오류", resolver_role: "self" }} onRetry={() => undefined} />);
    expect(screen.getByText("수정 후 재시도")).toBeTruthy();
  });
  it("이벤트가 없으면 요청 버튼이 비활성이고 이유가 붙는다", () => {
    render(<GateBlock error={{ gate: "G0", reason_code: "NOT_READY", reason: "준비 중", resolver_role: "operator", gate_event_id: null }} />);
    const btn = screen.getByText("운영 관리자에게 요청 보내기") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(screen.getByText(/이벤트가 기록되지 않아/)).toBeTruthy();
  });
});

describe("ResultCard", () => {
  it("확정 결과는 인원 / 정원 · 혼잡 % 를 크게, 여유 % 를 보조로 보인다 (R22)", () => {
    render(<ResultCard a={base} />);
    expect(screen.getByText("30 / 80명")).toBeTruthy();
    expect(screen.getByText("혼잡 38%")).toBeTruthy();
    expect(screen.getByText("여유 62%")).toBeTruthy();
    expect(screen.getByLabelText("혼잡 등급 여유")).toBeTruthy();
    expect(screen.getByText(/약 48명/)).toBeTruthy();
  });
  it("판독 불확실은 참고 접두 + 확정값 아님, 정원 없음은 산출 불가", () => {
    render(<ResultCard a={{ ...base, crowding_level: "uncertain", is_reference_only: true, mean_confidence: 0.52, warnings: [{ code: "blur" }] }} />);
    expect(screen.getByText("참고 30 / 80명")).toBeTruthy();
    expect(screen.getByText(/확정값 아님/)).toBeTruthy();
    render(<ResultCard a={{ ...base, capacity: null, remaining_persons: null, remaining_not_computable: true }} />);
    expect(screen.getByText("산출 불가")).toBeTruthy();
    expect(screen.getByText("혼잡도 산출 불가 (정원 미등록)")).toBeTruthy();
  });
  it("정원 초과는 100% 에서 멈추고 표시", () => {
    render(<ResultCard a={{ ...base, person_count: 90, occupied_area_ratio: 100, vacant_capacity_ratio: 0, over_capacity: true, remaining_persons: 0 }} />);
    expect(screen.getByText("혼잡 100% · 정원 초과")).toBeTruthy();
  });
});

describe("설계 번호는 화면에 보이지 않는다 (2026-09-30)", () => {
  it("운영 관리자에게도 차단 블록에 게이트 번호·사유 코드를 숨긴다", async () => {
    await asAdmin();
    render(<GateBlock error={{ gate: "G4", reason_code: "ROI_MISSING", reason: "ROI 없음", resolver_role: "operator", gate_event_id: 7 }} />);
    expect(screen.getByText("차단 상태")).toBeTruthy();
    expect(screen.queryByText(/G4|ROI_MISSING/)).toBeNull();
  });
  it("plain={false} 로 주면 번호를 보인다 (필요한 곳에서 켜는 길)", () => {
    render(<GateBlock plain={false} error={{ gate: "G4", reason_code: "ROI_MISSING", reason: "ROI 없음", resolver_role: "operator", gate_event_id: 7 }} />);
    expect(screen.getByText(/차단 상태 · G4 ROI_MISSING/)).toBeTruthy();
  });
});
