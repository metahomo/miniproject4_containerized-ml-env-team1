/* S6 실측 등록 — 카메라를 고르면 연결된 차량 번호가 채워진다 (2026-09-30 — 기본값 "1234" 로 G10 거부되던 문제) */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Measurement from "../src/pages/Measurement";

const res = (body: unknown) => ({ ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }) as unknown as Response;
const CAMS = [
  { camera_id: "CAM-DEMO-01", place_type: "bus_in", has_roi: true, roi_stale: false, has_capacity: true, has_mapping: true, vehicle_id: "대전75자2008" },
  { camera_id: "CAM-DEMO-02", place_type: "bus_in", has_roi: true, roi_stale: false, has_capacity: true, has_mapping: true, vehicle_id: "대전75자9018" },
  { camera_id: "CAM-X", place_type: "bus_in", has_roi: true, roi_stale: false, has_capacity: true, has_mapping: false, vehicle_id: null },
];

afterEach(() => vi.unstubAllGlobals());

describe("실측 등록 — 차량 번호 자동 채움", () => {
  it("주소의 camera_id 로 열면 그 카메라의 차량, 카메라를 바꾸면 그 차량, 연결 없으면 안내", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(CAMS)));
    render(<MemoryRouter initialEntries={["/admin/measurements?camera_id=CAM-DEMO-01"]}><Measurement /></MemoryRouter>);
    const vehicle = () => screen.getByLabelText(/차량 식별자/) as HTMLInputElement;
    await waitFor(() => expect(vehicle().value).toBe("대전75자2008"));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "CAM-DEMO-02" } });
    await waitFor(() => expect(vehicle().value).toBe("대전75자9018"));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "CAM-X" } });
    await waitFor(() => expect(vehicle().value).toBe(""));
    expect(screen.getByText(/연결된 차량이 없다/)).toBeTruthy();
  });
});
