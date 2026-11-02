/* C6 출처 드로어 — Esc 닫힘, 열릴 때 포커스 이동, 닫힐 때 원위치 */
import { useEffect, useRef } from "react";

export function SourceDrawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [onClose]);
  return (
    <>
      <div className="drawer-back" onClick={onClose} />
      <aside className="drawer stack" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 className="t-tagline">{title}</h3>
          <button className="btn btn-icon" onClick={onClose} aria-label="닫기">×</button>
        </div>
        {children}
      </aside>
    </>
  );
}
