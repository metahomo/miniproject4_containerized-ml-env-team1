/* 준비 상태 스토어 (U6, T022) — 30초 폴링. 서버 무응답이면 'unavailable' 로 취급 (§15-3). */
import { useEffect, useState } from "react";
import { ApiError, get } from "../api/client";
import type { Readiness } from "../api/types";

type Listener = (r: Readiness | null, offline: boolean) => void;
let current: Readiness | null = null;
let offline = false;
const listeners = new Set<Listener>();
let timer: number | undefined;

async function poll() {
  try {
    current = await get<Readiness>("/v1/readiness");
    offline = false;
  } catch (e) {
    offline = e instanceof ApiError && e.offline;
    if (offline) current = null;
  }
  listeners.forEach((l) => l(current, offline));
}

export function refreshReadiness() {
  return poll();
}

export function useReadiness(): { readiness: Readiness | null; offline: boolean; ready: boolean; refresh: () => Promise<void> } {
  const [state, setState] = useState<{ r: Readiness | null; o: boolean }>({ r: current, o: offline });
  useEffect(() => {
    const l: Listener = (r, o) => setState({ r, o });
    listeners.add(l);
    if (!timer) {
      poll();
      timer = window.setInterval(poll, 30000);
    }
    return () => {
      listeners.delete(l);
    };
  }, []);
  return { readiness: state.r, offline: state.o, ready: state.r?.readiness === "ready", refresh: poll };
}
