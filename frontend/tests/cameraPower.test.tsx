/* S2b 카메라 전원 관리 표 + 노트북 카메라가 화면을 떠나도 꺼지지 않는지 */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Cameras from "../src/pages/admin/Cameras";
import { WebcamDiagnosis } from "../src/components/WebcamDiagnosis";
import { getWebcam, startWebcam, stopWebcam } from "../src/stores/webcam";

const row = (o: Record<string, unknown>) => ({
  camera_id: "CAM", mode: "bus", place_type: "bus_in", route_id: "R", route_name: "102번 (30300037)", vehicle_id: null, car_position: null,
  run_state: null, capacity: 48, persons: null, density: null, crowding_level: null, last_diagnosed_at: null, powered: false, powered_at: null,
  operation: "off", frame_source: null, poll_interval_s: 10, last_error: null, ...o,
});
const ROWS = [
  row({ camera_id: "CAM-T1", mode: "rail", place_type: "train_in", route_name: "1호선", vehicle_id: "2145", car_position: 1, run_state: "running", capacity: 160, persons: 20, density: 12.5, powered: true, operation: "normal" }),
  row({ camera_id: "CAM-B1", vehicle_id: "대전75자2046", run_state: "running", persons: 20, density: 41.7, powered: false, operation: "off" }),
];
const json = (body: unknown) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) }) as unknown as Response;

afterEach(() => { vi.unstubAllGlobals(); act(() => stopWebcam()); });

describe("카메라 전원 관리", () => {
  it("지하철·버스 표를 나눠 보이고 on/off 가 전원 API 를 부른다", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/power")) return json({ ...ROWS[1], powered: JSON.parse(String(init?.body)).on, operation: "offline" });
      if (url.includes("/v1/web/samples")) return json([]);
      return json(ROWS);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><Cameras /></MemoryRouter>);
    const rail = await screen.findByRole("region", { name: "지하철" });
    await waitFor(() => expect(within(rail).getByText("2145")).toBeTruthy());
    expect(within(rail).getByText("1칸")).toBeTruthy();
    expect(within(rail).getByText("12.5%")).toBeTruthy();
    expect(within(rail).getByText(/정상 작동/)).toBeTruthy();
    const bus = screen.getByRole("region", { name: "버스" });
    expect(within(bus).getByText("102번 · 대전75자2046")).toBeTruthy();
    expect(within(bus).getByText(/꺼짐/)).toBeTruthy();
    fireEvent.click(within(bus).getByRole("switch", { name: "CAM-B1 전원" }));
    await waitFor(() => expect(within(bus).getByRole("switch", { name: "CAM-B1 전원" }).getAttribute("aria-checked")).toBe("true"));
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/v1/admin/cameras/CAM-B1/power"))!;
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({ on: true });
  });
});

describe("노트북 카메라 세션", () => {
  it("진단 화면이 사라져도 카메라를 끄지 않는다 — «카메라 끄기»에서만 끈다", async () => {
    const track = { stop: vi.fn(), addEventListener: vi.fn() };
    const stream = { getTracks: () => [track], getVideoTracks: () => [track] } as unknown as MediaStream;
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn(async () => stream) } });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(async () => undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const view = render(<WebcamDiagnosis cameraId="CAM-WEBCAM" interval={1} enabled onGate={() => undefined} onSelect={() => undefined} />);
    await act(async () => { await startWebcam(); });
    expect(getWebcam().stream).toBe(stream);
    view.unmount();                                   // 다른 메뉴·다른 탭으로 이동
    expect(getWebcam().stream).toBe(stream);
    expect(track.stop).not.toHaveBeenCalled();
    expect(getWebcam().cameraId).toBe("CAM-WEBCAM");
    act(() => stopWebcam());
    expect(track.stop).toHaveBeenCalled();
    expect(getWebcam().stream).toBeNull();
  });
});
