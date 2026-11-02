/* S5 샘플 선택 — 목록 표시, 고르면 서버 파일을 File 로 넘김, 샘플이 없으면 숨김 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SamplePicker } from "../src/components/SamplePicker";
import type { SampleMedia } from "../src/api/types";

const items: SampleMedia[] = [
  { file: "videos/a.webm", title: "역 대합실 · 혼잡", kind: "video", bytes: 2 * 1024 * 1024, content_type: "video/webm",
    source_url: "https://commons.wikimedia.org/wiki/File:A.webm", license: "CC0", author: "tester" },
];

const mockFetch = (list: SampleMedia[]) =>
  vi.fn(async (url: string) => (url.endsWith("/v1/web/samples")
    ? new Response(JSON.stringify(list), { status: 200 })
    : new Response(new Blob(["vid"], { type: "video/webm" }), { status: 200 })));

afterEach(() => vi.unstubAllGlobals());

describe("SamplePicker", () => {
  it("샘플을 고르면 서버 파일을 받아 File 로 넘긴다", async () => {
    const f = mockFetch(items);
    vi.stubGlobal("fetch", f);
    const onPick = vi.fn();
    render(<SamplePicker value="" onPick={onPick} />);
    await screen.findByText(/역 대합실 · 혼잡/);
    fireEvent.change(screen.getByLabelText("샘플 선택"), { target: { value: "videos/a.webm" } });
    await waitFor(() => expect(onPick).toHaveBeenCalled());
    const [name, file] = onPick.mock.calls[0];
    expect(name).toBe("videos/a.webm");
    expect(file).toBeInstanceOf(File);
    expect((file as File).name).toBe("a.webm");
    expect((file as File).type).toBe("video/webm");
    expect(String(f.mock.calls[1][0])).toContain("/v1/web/samples/videos/a.webm");
  });

  it("고른 샘플의 출처·라이선스를 표시한다", async () => {
    vi.stubGlobal("fetch", mockFetch(items));
    render(<SamplePicker value="videos/a.webm" onPick={() => undefined} />);
    expect((await screen.findByText("tester")).getAttribute("href")).toBe(items[0].source_url);
    expect(screen.getByText(/CC0/)).toBeTruthy();
  });

  it("서버에 샘플이 없으면 아무것도 그리지 않는다", async () => {
    const f = mockFetch([]);
    vi.stubGlobal("fetch", f);
    const { container } = render(<SamplePicker value="" onPick={() => undefined} />);
    await waitFor(() => expect(f).toHaveBeenCalled());
    await waitFor(() => expect(container.innerHTML).toBe(""));
  });
});
