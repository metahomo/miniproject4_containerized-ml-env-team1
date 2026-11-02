/* 어두운 관제 콘솔 시안 켜기·끄기 (디자인 시안 2026-11-02). 기본은 콘솔, «밝은 화면»을 고르면 이 브라우저에 기억한다. */
import { useSyncExternalStore } from "react";

const KEY = "cv.theme";
const listeners = new Set<() => void>();

let consoleOn = (() => {
  try { return localStorage.getItem(KEY) !== "light"; } catch { return true; }
})();

export function toggleConsole() {
  consoleOn = !consoleOn;
  try { localStorage.setItem(KEY, consoleOn ? "console" : "light"); } catch { /* 저장 못 해도 이번 화면에는 적용 */ }
  listeners.forEach((fn) => fn());
}

export const useConsole = () => useSyncExternalStore((fn) => { listeners.add(fn); return () => { listeners.delete(fn); }; }, () => consoleOn);

export function ThemeToggle() {
  const on = useConsole();
  return <button type="button" className="btn btn-pearl theme-toggle" aria-pressed={on} onClick={toggleConsole}>{on ? "밝은 화면" : "콘솔 시안"}</button>;
}
