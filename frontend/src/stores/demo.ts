/* 시연 모드 스토어 — 이용자 조회 경로 /v1/reference/ops-status 로 demo_on·demo_end_at 을 60초마다 읽는다 (T095: 관리자 키 없이도 표시). */
import { useEffect, useState } from "react";
import { get } from "../api/client";
import type { OpsStatus } from "../api/types";

export interface DemoState { known: boolean; on: boolean; endAt?: string | null }
let current: DemoState = { known: false, on: false };
const listeners = new Set<(d: DemoState) => void>();
let timer: number | undefined;

async function poll() {
  try {
    const v = await get<OpsStatus>("/v1/reference/ops-status");
    current = { known: true, on: !!v.demo_on, endAt: v.demo_end_at ?? null };
  } catch {
    current = { ...current, known: false };
  }
  listeners.forEach((l) => l(current));
}

export const refreshDemo = () => poll();

export function useDemo(): DemoState & { refresh: () => Promise<void> } {
  const [s, setS] = useState(current);
  useEffect(() => {
    listeners.add(setS);
    if (!timer) {
      poll();
      timer = window.setInterval(poll, 60000);
    }
    return () => {
      listeners.delete(setS);
    };
  }, []);
  return { ...s, refresh: poll };
}
