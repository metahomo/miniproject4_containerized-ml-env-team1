/* 로그인 화면 (T108) — 사이트에 들어오면 먼저 로그인한다. 회원가입하면 바로 일반 사용자.
   2026-09-30: 설명문 삭제 — 아이디·비밀번호·로그인·회원가입만. */
import { useEffect, useRef } from "react";
import { LoginForm } from "../components/AdminLogin";
import { FAR, MID, NEAR, SCENE_DEFS } from "../components/loginScene";

/* 배경: 펠트 동물 버스 그림(시안 4, 2026-09-30 사용자 확정) — 마우스를 따라 3D 로 조금씩 늦게 움직인다.
   레이어마다 깊이가 달라 움직이는 거리가 다르고(먼 배경은 반대로, 버스·앞쪽 도로는 마우스 쪽으로), 장면 전체가 원근 있게 살짝 기운다.
   움직임 줄이기 설정·터치면 따라 움직이지 않는다. 위치는 CSS 변수 --mx·--my(-1…1)로만 넘긴다. */
function useParallax() {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    let tx = 0, ty = 0, x = 0, y = 0, raf = 0;
    const tick = () => {
      x += (tx - x) * 0.06; y += (ty - y) * 0.06;   // 느리게 따라온다
      el.style.setProperty("--mx", x.toFixed(4)); el.style.setProperty("--my", y.toFixed(4));
      raf = Math.abs(tx - x) + Math.abs(ty - y) > 0.001 ? requestAnimationFrame(tick) : 0;
    };
    const move = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      tx = (e.clientX / window.innerWidth) * 2 - 1; ty = (e.clientY / window.innerHeight) * 2 - 1;
      if (!raf) raf = requestAnimationFrame(tick);
    };
    const leave = () => { tx = 0; ty = 0; if (!raf) raf = requestAnimationFrame(tick); };
    window.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    return () => { window.removeEventListener("pointermove", move); document.documentElement.removeEventListener("pointerleave", leave); cancelAnimationFrame(raf); };
  }, []);
  return ref;
}

export function AuthShell({ children }: { children: React.ReactNode }) {
  const ref = useParallax();
  return (
    <main className="auth-shell" ref={ref}>
      <div className="auth-bg" aria-hidden>
        <svg width="0" height="0" style={{ position: "absolute" }} dangerouslySetInnerHTML={{ __html: `<defs>${SCENE_DEFS}</defs>` }} />
        <div className="auth-scene">
          <div className="auth-layer far" dangerouslySetInnerHTML={{ __html: FAR }} />
          <div className="auth-layer mid" dangerouslySetInnerHTML={{ __html: MID }} />
          <div className="auth-layer near" dangerouslySetInnerHTML={{ __html: NEAR }} />
        </div>
        <div className="auth-lift" />
      </div>
      <div className="auth-inner">
        <h1 className="auth-title">대전 버스 혼잡도</h1>
        <p className="auth-sub">타려는 버스가 언제 오는지, 얼마나 찼는지</p>
        {children}
      </div>
    </main>
  );
}

export default function Login() {
  return (
    <AuthShell>
      <section className="auth-card stack" aria-label="로그인 화면">
        <LoginForm autoFocus />
      </section>
    </AuthShell>
  );
}
