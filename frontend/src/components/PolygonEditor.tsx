/* ROI 다각형 편집기 — 배경 프레임은 브라우저 메모리(objectURL)에만 두고 서버로 보내지 않는다 (U8). 클릭으로 꼭짓점 추가, 우클릭/버튼으로 마지막 점 제거. */
import { useEffect, useRef, useState } from "react";

export function PolygonEditor({ points, onChange, imageUrl, width = 640 }: { points: number[][]; onChange: (p: number[][]) => void; imageUrl?: string | null; width?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [natural, setNatural] = useState<[number, number]>([1280, 720]);

  useEffect(() => {
    if (!imageUrl) { setImg(null); return; }
    const im = new Image();
    im.onload = () => { setImg(im); setNatural([im.naturalWidth, im.naturalHeight]); };
    im.src = imageUrl;
    return () => { im.onload = null; };
  }, [imageUrl]);

  const scale = width / natural[0];
  const height = Math.round(natural[1] * scale);

  useEffect(() => {
    const c = canvas.current; if (!c) return;
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, width, height);
    if (img) ctx.drawImage(img, 0, 0, width, height);
    else { ctx.fillStyle = "#e9e9ec"; ctx.fillRect(0, 0, width, height); ctx.fillStyle = "#7a7a7a"; ctx.font = "14px sans-serif"; ctx.fillText("프레임을 선택하면 배경으로 표시 (서버에 전송되지 않음)", 16, 24); }
    if (points.length) {
      ctx.beginPath();
      points.forEach(([x, y], i) => (i ? ctx.lineTo(x * scale, y * scale) : ctx.moveTo(x * scale, y * scale)));
      if (points.length > 2) ctx.closePath();
      ctx.fillStyle = "rgba(0,102,204,.18)"; ctx.fill();
      ctx.strokeStyle = "#0066cc"; ctx.lineWidth = 2; ctx.stroke();
      points.forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x * scale, y * scale, 5, 0, Math.PI * 2); ctx.fillStyle = "#0066cc"; ctx.fill(); });
    }
  }, [img, points, scale, width, height]);

  const add = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const r = canvas.current!.getBoundingClientRect();
    const x = Math.round((e.clientX - r.left) / scale), y = Math.round((e.clientY - r.top) / scale);
    onChange([...points, [x, y]]);
  };
  return (
    <div className="stack">
      <canvas ref={canvas} width={width} height={height} style={{ border: "1px solid var(--color-hairline)", borderRadius: 8, cursor: "crosshair", maxWidth: "100%" }} onClick={add} onContextMenu={(e) => { e.preventDefault(); onChange(points.slice(0, -1)); }} aria-label="ROI 다각형 편집 캔버스" />
      <div className="row t-caption">
        <span className="muted">클릭: 꼭짓점 추가 · 우클릭: 마지막 점 제거 · 원본 픽셀 {natural[0]}×{natural[1]}</span>
        <button type="button" className="btn btn-pearl" onClick={() => onChange(points.slice(0, -1))} disabled={!points.length}>마지막 점 제거</button>
        <button type="button" className="btn btn-pearl" onClick={() => onChange([])} disabled={!points.length}>모두 지우기</button>
      </div>
    </div>
  );
}
