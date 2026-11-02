/* 로그인·회원가입 배경 그림 (2026-09-30 사용자 시안 4 확정) — 흐린 대전 거리 + 펠트 콜라주 102번 버스, 동물 승객(적당히 참).
   세 레이어(먼 배경·버스·앞쪽 도로)를 따로 그려 AuthShell 이 마우스를 따라 깊이를 다르게 움직인다(3D 시차 + 원근 기울기).
   참조 그림은 분위기·재질만 참고했고 그림은 새로 그렸다. SVG 문자열은 모듈을 불러올 때 한 번만 만든다. */

/** 공용 필터·무늬 — 세 레이어가 id 로 참조한다 (한 문서에 한 번만 넣는다) */
export const SCENE_DEFS = `<filter id="dof" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="16"/></filter>
    <filter id="dof2" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7"/></filter>
    <filter id="ao" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
    <filter id="asphalt" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="3" seed="5" result="t"/>
      <feColorMatrix in="t" type="matrix" values="0 0 0 0 0.25  0 0 0 0 0.26  0 0 0 0 0.28  0.55 0 0 0 -0.12" result="dots"/>
      <feComposite in="dots" in2="SourceGraphic" operator="in" result="d2"/>
      <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="d2"/></feMerge>
    </filter>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e3ebee"/><stop offset=".6" stop-color="#eef0ec"/></linearGradient>
    <linearGradient id="road" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c3c6ca"/><stop offset="1" stop-color="#a9adb3"/></linearGradient>
    <filter id="felt" x="-3%" y="-3%" width="106%" height="106%">
      <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="3" result="w"/>
      <feDisplacementMap in="SourceGraphic" in2="w" scale="2.5" xChannelSelector="R" yChannelSelector="G" result="src"/>
      <feTurbulence type="fractalNoise" baseFrequency="1.3" numOctaves="3" seed="12" result="t"/>
      <feColorMatrix in="t" type="matrix" values="0 0 0 0 0.2  0 0 0 0 0.2  0 0 0 0 0.2  0.9 0 0 0 -0.38" result="dk"/>
      <feColorMatrix in="t" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0.9 0 0 -0.42" result="lt"/>
      <feComposite in="dk" in2="src" operator="in" result="dk2"/><feComposite in="lt" in2="src" operator="in" result="lt2"/>
      <feMerge><feMergeNode in="src"/><feMergeNode in="dk2"/><feMergeNode in="lt2"/></feMerge>
    </filter>
    <pattern id="wood" width="120" height="26" patternUnits="userSpaceOnUse"><rect width="120" height="26" fill="#e3a93a"/><path d="M0 7 Q30 3 60 8 T120 6 M0 15 Q40 12 70 17 T120 14 M0 22 Q30 19 60 23 T120 21" stroke="#c98a22" stroke-width="1.6" fill="none" opacity=".8"/></pattern>
    <pattern id="herring" width="16" height="16" patternUnits="userSpaceOnUse"><rect width="16" height="16" fill="#5e9e8f"/><path d="M0 8 L8 0 M8 16 L16 8 M8 0 L16 8 M0 8 L8 16" stroke="#7fbcad" stroke-width="2.2"/></pattern>
    <pattern id="gingham" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" fill="#f4f1ea"/><rect width="7" height="14" fill="#8fc5d6" opacity=".6"/><rect width="14" height="7" fill="#8fc5d6" opacity=".6"/></pattern>
    <pattern id="knit" width="10" height="10" patternUnits="userSpaceOnUse"><rect width="10" height="10" fill="#565b64"/><path d="M1 2 L5 8 L9 2" stroke="#6c727c" stroke-width="2" fill="none"/></pattern>
    <pattern id="lace" width="18" height="18" patternUnits="userSpaceOnUse"><rect width="18" height="18" fill="#f5f3ee"/><circle cx="9" cy="9" r="4" fill="none" stroke="#d9d5cb" stroke-width="1.5"/><circle cx="0" cy="0" r="2" fill="#d9d5cb"/><circle cx="18" cy="18" r="2" fill="#d9d5cb"/></pattern>`;

const V = 'viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg"';

/* ── 시안 4: 펠트 콜라주 버스 + 동물 승객 (적당히 참) ── */
const F = 'filter="url(#felt)"';
const eyes = (cx: number, cy: number, r: number, gap = .34) => `<circle cx="${cx - r * gap}" cy="${cy}" r="${r * .085}" fill="#2a2320"/><circle cx="${cx + r * gap}" cy="${cy}" r="${r * .085}" fill="#2a2320"/>`;
const smile = (cx: number, cy: number, r: number) => `<path d="M${cx - r * .16} ${cy} Q${cx} ${cy + r * .14} ${cx + r * .16} ${cy}" stroke="#2a2320" stroke-width="${r * .06}" fill="none" stroke-linecap="round"/>`;
const cheeks = (cx: number, cy: number, r: number) => `<circle cx="${cx - r * .55}" cy="${cy}" r="${r * .14}" fill="#f29bb0" opacity=".7"/><circle cx="${cx + r * .55}" cy="${cy}" r="${r * .14}" fill="#f29bb0" opacity=".7"/>`;
const torso = (cx: number, cy: number, r: number, fill: string) => `<path d="M${cx - r * 1.15} ${cy + r * 3.2} L${cx - r * 1.1} ${cy + r * 1.35} Q${cx - r * 1.05} ${cy + r * .78} ${cx} ${cy + r * .78} Q${cx + r * 1.05} ${cy + r * .78} ${cx + r * 1.1} ${cy + r * 1.35} L${cx + r * 1.15} ${cy + r * 3.2}Z" fill="${fill}" ${F}/>`;
const A: Record<string, (cx: number, cy: number, r: number) => string> = {
  bear: (cx, cy, r) => torso(cx, cy, r, "url(#knit)") + `<path d="M${cx - r * .7} ${cy + r * .9} L${cx - r * .75} ${cy + r * 3}" stroke="#e58fae" stroke-width="${r * .14}"/><path d="M${cx + r * .7} ${cy + r * .9} L${cx + r * .75} ${cy + r * 3}" stroke="#e58fae" stroke-width="${r * .14}"/>
    <g ${F}><circle cx="${cx - r * .72}" cy="${cy - r * .72}" r="${r * .36}" fill="#8b5a35"/><circle cx="${cx + r * .72}" cy="${cy - r * .72}" r="${r * .36}" fill="#8b5a35"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="#94623b"/><ellipse cx="${cx}" cy="${cy + r * .32}" rx="${r * .46}" ry="${r * .32}" fill="#d9b48b"/></g>
    <circle cx="${cx - r * .72}" cy="${cy - r * .72}" r="${r * .17}" fill="#c48d62"/><circle cx="${cx + r * .72}" cy="${cy - r * .72}" r="${r * .17}" fill="#c48d62"/>
    ${eyes(cx, cy - r * .12, r)}<ellipse cx="${cx}" cy="${cy + r * .2}" rx="${r * .14}" ry="${r * .1}" fill="#2a2320"/>${smile(cx, cy + r * .38, r)}`,
  rabbit: (cx, cy, r) => torso(cx, cy, r, "#e98fb0") + `<g ${F}><ellipse cx="${cx - r * .38}" cy="${cy - r * 1.35}" rx="${r * .24}" ry="${r * .75}" fill="#f7f5f0"/><ellipse cx="${cx + r * .38}" cy="${cy - r * 1.35}" rx="${r * .24}" ry="${r * .75}" fill="#f7f5f0"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="#f7f5f0"/></g>
    <ellipse cx="${cx - r * .38}" cy="${cy - r * 1.3}" rx="${r * .1}" ry="${r * .5}" fill="#f4b3c6"/><ellipse cx="${cx + r * .38}" cy="${cy - r * 1.3}" rx="${r * .1}" ry="${r * .5}" fill="#f4b3c6"/>
    <path d="M${cx - r * .75} ${cy - r * .55} Q${cx} ${cy - r * 1.25} ${cx + r * .75} ${cy - r * .55} Q${cx} ${cy - r * .8} ${cx - r * .75} ${cy - r * .55}Z" fill="#9d86c7" ${F}/>
    ${eyes(cx, cy - r * .05, r)}${cheeks(cx, cy + r * .25, r)}<path d="M${cx - r * .08} ${cy + r * .18} L${cx + r * .08} ${cy + r * .18} L${cx} ${cy + r * .28}Z" fill="#e57795"/>`,
  pig: (cx, cy, r) => torso(cx, cy, r, "#e2563f") + `<path d="M${cx - r * .25} ${cy + r * 1} L${cx} ${cy + r * 1.12} L${cx + r * .25} ${cy + r * 1} L${cx + r * .25} ${cy + r * 1.28} L${cx} ${cy + r * 1.16} L${cx - r * .25} ${cy + r * 1.28}Z" fill="#f2994a"/>
    <g ${F}><path d="M${cx - r * .95} ${cy - r * .35} L${cx - r * .75} ${cy - r * 1.15} L${cx - r * .25} ${cy - r * .8}Z" fill="#ef8fb4"/><path d="M${cx + r * .95} ${cy - r * .35} L${cx + r * .75} ${cy - r * 1.15} L${cx + r * .25} ${cy - r * .8}Z" fill="#ef8fb4"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="#f3a6c4"/><ellipse cx="${cx}" cy="${cy + r * .28}" rx="${r * .36}" ry="${r * .24}" fill="#f7c3d6"/></g>
    <circle cx="${cx - r * .12}" cy="${cy + r * .28}" r="${r * .06}" fill="#b0476d"/><circle cx="${cx + r * .12}" cy="${cy + r * .28}" r="${r * .06}" fill="#b0476d"/>${eyes(cx, cy - r * .18, r, .4)}`,
  mouse: (cx, cy, r) => torso(cx, cy, r, "#6f9a4a") + `<circle cx="${cx - r * .55}" cy="${cy + r * 1.6}" r="${r * .12}" fill="#8a6a3e"/><circle cx="${cx + r * .55}" cy="${cy + r * 1.6}" r="${r * .12}" fill="#8a6a3e"/>
    <g ${F}><circle cx="${cx - r * .85}" cy="${cy - r * .7}" r="${r * .55}" fill="#d6cfbd"/><circle cx="${cx + r * .85}" cy="${cy - r * .7}" r="${r * .55}" fill="#d6cfbd"/><ellipse cx="${cx}" cy="${cy}" rx="${r * .9}" ry="${r}" fill="#dcd6c5"/></g>
    <circle cx="${cx - r * .85}" cy="${cy - r * .7}" r="${r * .3}" fill="#efc2c9"/><circle cx="${cx + r * .85}" cy="${cy - r * .7}" r="${r * .3}" fill="#efc2c9"/>
    ${eyes(cx, cy - r * .08, r, .3)}<circle cx="${cx}" cy="${cy + r * .25}" r="${r * .1}" fill="#2a2320"/>
    <path d="M${cx - r * .2} ${cy + r * .3} H${cx - r * .75} M${cx - r * .2} ${cy + r * .38} L${cx - r * .7} ${cy + r * .5} M${cx + r * .2} ${cy + r * .3} H${cx + r * .75} M${cx + r * .2} ${cy + r * .38} L${cx + r * .7} ${cy + r * .5}" stroke="#6b645a" stroke-width="${r * .035}"/>`,
  owl: (cx, cy, r) => `<g ${F}><path d="M${cx - r * 1.05} ${cy + r * 3} Q${cx - r * 1.2} ${cy - r * .6} ${cx - r * .8} ${cy - r * 1.1} L${cx - r * .5} ${cy - r * .8} Q${cx} ${cy - r * 1} ${cx + r * .5} ${cy - r * .8} L${cx + r * .8} ${cy - r * 1.1} Q${cx + r * 1.2} ${cy - r * .6} ${cx + r * 1.05} ${cy + r * 3}Z" fill="#6f86b8"/>
    <ellipse cx="${cx}" cy="${cy + r * 1.5}" rx="${r * .7}" ry="${r * 1.1}" fill="#aebbd8"/></g>
    ${[0, 1, 2].map((i) => `<path d="M${cx - r * .4} ${cy + r * (1.1 + i * .4)} q${r * .2} ${r * .2} ${r * .4} 0 q${r * .2} ${r * .2} ${r * .4} 0" stroke="#7f8fb8" stroke-width="${r * .06}" fill="none"/>`).join("")}
    <circle cx="${cx - r * .38}" cy="${cy - r * .1}" r="${r * .33}" fill="#f4f1e8"/><circle cx="${cx + r * .38}" cy="${cy - r * .1}" r="${r * .33}" fill="#f4f1e8"/>
    <circle cx="${cx - r * .38}" cy="${cy - r * .1}" r="${r * .13}" fill="#2a2320"/><circle cx="${cx + r * .38}" cy="${cy - r * .1}" r="${r * .13}" fill="#2a2320"/>
    <path d="M${cx - r * .1} ${cy + r * .22} L${cx + r * .1} ${cy + r * .22} L${cx} ${cy + r * .42}Z" fill="#f2a33a"/>`,
  dog: (cx, cy, r) => torso(cx, cy, r, "url(#gingham)") + `<g ${F}><circle cx="${cx}" cy="${cy}" r="${r}" fill="#f1e4c8"/><ellipse cx="${cx - r * .95}" cy="${cy + r * .05}" rx="${r * .3}" ry="${r * .62}" fill="#a06e45" transform="rotate(18 ${cx - r * .95} ${cy})"/><ellipse cx="${cx + r * .95}" cy="${cy + r * .05}" rx="${r * .3}" ry="${r * .62}" fill="#a06e45" transform="rotate(-18 ${cx + r * .95} ${cy})"/>
    <ellipse cx="${cx + r * .35}" cy="${cy - r * .25}" rx="${r * .28}" ry="${r * .24}" fill="#d9b88f"/></g>
    ${eyes(cx, cy - r * .12, r)}<ellipse cx="${cx}" cy="${cy + r * .22}" rx="${r * .15}" ry="${r * .11}" fill="#2a2320"/>${smile(cx, cy + r * .4, r)}`,
  cat: (cx, cy, r) => torso(cx, cy, r, "#3f5a86") + `<g ${F}><path d="M${cx - r * .95} ${cy - r * .2} L${cx - r * .8} ${cy - r * 1.15} L${cx - r * .2} ${cy - r * .85}Z" fill="#e9a55b"/><path d="M${cx + r * .95} ${cy - r * .2} L${cx + r * .8} ${cy - r * 1.15} L${cx + r * .2} ${cy - r * .85}Z" fill="#e9a55b"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="#efb069"/></g>
    <path d="M${cx - r * .9} ${cy - r * .55} Q${cx} ${cy - r * 1.35} ${cx + r * .9} ${cy - r * .55}Z" fill="#35507a" ${F}/><rect x="${cx - r * .2}" y="${cy - r * .62}" width="${r * 1.35}" height="${r * .18}" rx="${r * .09}" fill="#2b4166"/>
    ${eyes(cx, cy, r)}<path d="M${cx - r * .07} ${cy + r * .22} L${cx + r * .07} ${cy + r * .22} L${cx} ${cy + r * .31}Z" fill="#c9675b"/>
    <path d="M${cx - r * .2} ${cy + r * .32} H${cx - r * .8} M${cx + r * .2} ${cy + r * .32} H${cx + r * .8}" stroke="#7a5230" stroke-width="${r * .04}"/>`,
  seat: (cx, cy, r) => `<rect x="${cx - r * .95}" y="${cy + r * .2}" width="${r * 1.9}" height="${r * 3}" rx="${r * .4}" fill="#a7b0b6" ${F}/><rect x="${cx - r * .75}" y="${cy + r * .4}" width="${r * 1.5}" height="${r * .5}" rx="${r * .2}" fill="#c3cad0"/>`,
  bird: (cx, cy, r) => `<ellipse cx="${cx}" cy="${cy}" rx="${r}" ry="${r * .7}" fill="#8a5b3d" ${F}/><circle cx="${cx + r * .8}" cy="${cy - r * .45}" r="${r * .45}" fill="#8a5b3d" ${F}/><path d="M${cx + r * 1.2} ${cy - r * .5} l${r * .45} ${r * .1} l-${r * .45} ${r * .15}Z" fill="#f2a33a"/><circle cx="${cx + r * .9}" cy="${cy - r * .55}" r="${r * .08}" fill="#fff"/><path d="M${cx - r} ${cy} l-${r * .7} -${r * .3}" stroke="#5e3e2a" stroke-width="${r * .25}" stroke-linecap="round"/>`,
};
const coil = (cx: number, cy: number, R: number) => {
  let d = ""; for (let t = 0; t <= 7 * Math.PI * 2; t += .25) { const rr = 3 + (R - 3) * t / (14 * Math.PI); d += (d ? "L" : "M") + (cx + rr * Math.cos(t)).toFixed(1) + " " + (cy + rr * Math.sin(t)).toFixed(1); }
  return `<circle cx="${cx}" cy="${cy}" r="${R + 2}" fill="#e9e0c9" ${F}/><path d="${d}" stroke="#f6efdd" stroke-width="5.5" fill="none" stroke-linecap="round"/><path d="${d}" stroke="#cbbf9f" stroke-width="1.3" fill="none" stroke-dasharray="3 4"/>`;
};
const spoke = (cx: number, cy: number, R: number) => `<circle cx="${cx}" cy="${cy}" r="${R}" fill="#8aa04a" ${F}/><circle cx="${cx}" cy="${cy}" r="${R - 9}" fill="#f5f1e6"/>
  ${Array.from({ length: 16 }, (_, i) => { const a = i * Math.PI / 8; return `<path d="M${cx} ${cy} L${(cx + (R - 9) * Math.cos(a)).toFixed(1)} ${(cy + (R - 9) * Math.sin(a)).toFixed(1)}" stroke="#3d3a35" stroke-width="1.3"/>`; }).join("")}<circle cx="${cx}" cy="${cy}" r="5" fill="#3d3a35"/>`;
function bus(X: number, Y: number): string {
  const body = "M10 44 Q10 14 42 12 L772 8 Q806 8 826 32 L884 96 Q906 116 906 146 L904 184 Q902 204 878 204 L34 206 Q8 206 8 182 Z";
  const panes = [["bear", "seat"], ["rabbit", "pig"], ["seat", "mouse"], ["owl", "seat"], ["dog"], ["seat"]];
  let win = "";
  panes.forEach((who, i) => {
    const x = 40 + i * 124, w = 112, y = 36, h = 92, id = `fp${i}`;
    const inner = who.map((a, j) => A[a](x + (j + .5) * w / who.length + (who.length === 1 ? 0 : (j ? 3 : -3)), y + 50 + (a === "owl" ? 4 : 0), a === "seat" ? 21 : a === "mouse" ? 19 : 22)).join("");
    win += `<clipPath id="${id}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12"/></clipPath>
      <g clip-path="url(#${id})"><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#eceeed" ${F}/>${inner}
      <path d="M${x + w * .7} ${y} L${x + w * .45} ${y + h}" stroke="#fff" stroke-width="10" opacity=".35"/></g>
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="none" stroke="#9ea4a8" stroke-width="4" ${F}/>`;
  });
  return `<g transform="translate(${X} ${Y})">
    <ellipse cx="455" cy="232" rx="470" ry="24" fill="#1d232b" opacity=".32" filter="url(#ao)"/>
    <clipPath id="fbody"><path d="${body}"/></clipPath>
    <g clip-path="url(#fbody)">
      <rect x="0" y="0" width="910" height="210" fill="#bcc1c4" ${F}/>
      <rect x="0" y="146" width="910" height="30" fill="url(#herring)" ${F}/>
      <rect x="0" y="176" width="910" height="30" fill="url(#lace)" ${F}/>
    </g>
    <path d="M22 140 Q22 26 50 24 L770 22 Q798 22 814 42 L866 102 Q884 118 886 140 Z" fill="none" stroke="#e8743b" stroke-width="3" stroke-dasharray="11 8" stroke-linecap="round"/>
    <path d="M18 -6 Q20 -18 44 -18 L760 -20 Q800 -18 812 4 L800 16 L30 18 Q18 18 18 6Z" fill="url(#wood)" ${F}/>
    ${win}
    <path d="M792 30 L818 30 L872 94 L874 132 L792 132Z" fill="#eceeed" ${F}/>
    <g clip-path="url(#fbody)">${A.cat(832, 86, 21)}</g>
    <path d="M792 30 L818 30 L872 94 L874 132 L792 132Z" fill="none" stroke="#9ea4a8" stroke-width="4" ${F}/>
    <circle cx="858" cy="126" r="16" fill="none" stroke="#3d3a35" stroke-width="4"/>
    <g transform="rotate(-2 440 170)"><rect x="340" y="152" width="200" height="30" rx="3" fill="#f5efdc" ${F}/><text x="440" y="174" text-anchor="middle" font-family="sans-serif" font-weight="800" font-size="19" fill="#5aa36a">102 충남대학교</text></g>
    <g transform="translate(730 -40)"><rect width="66" height="40" rx="8" fill="#2f4f86"/><rect x="5" y="5" width="56" height="30" rx="5" fill="#5f9e7a" stroke="#fff" stroke-width="1.5" stroke-dasharray="3 3"/><text x="33" y="27" text-anchor="middle" font-family="sans-serif" font-weight="800" font-size="17" fill="#fff">102</text></g>
    <g transform="translate(888 160)"><circle r="13" fill="#e9d8b0" stroke="#8a7a58" stroke-width="2"/>${[[-4, -4], [4, -4], [-4, 4], [4, 4]].map(([a, b]) => `<circle cx="${a}" cy="${b}" r="2" fill="#6b5d40"/>`).join("")}</g>
    <rect x="0" y="150" width="10" height="26" rx="4" fill="#e0785f"/>
    ${A.bird(420, -30, 12)}
    ${coil(190, 208, 44)}${spoke(732, 208, 46)}
  </g>`;
}

export const FAR = `<svg ${V}>
  <rect width="1600" height="900" fill="url(#bg)"/>
  <g filter="url(#dof)">
    <rect x="60" y="250" width="220" height="360" fill="#dfe3e6"/><rect x="330" y="300" width="180" height="310" fill="#e8e4dc"/><rect x="1080" y="270" width="200" height="340" fill="#e0e5e9"/><rect x="1330" y="320" width="220" height="290" fill="#e9e5de"/>
    <rect x="560" y="230" width="160" height="380" fill="#e4e7ea"/><rect x="760" y="290" width="130" height="320" fill="#ebe7e0"/><rect x="930" y="250" width="120" height="360" fill="#dfe4e8"/>
    ${([[90,430,150,200,"#a9c9a6"],[250,500,90,110,"#c3d9b9"],[420,470,130,150,"#b3cfac"],[600,520,80,90,"#cfe0c5"],[720,450,120,170,"#9fc19c"],[880,510,90,100,"#c6dbbd"],
       [1000,460,140,160,"#afcca9"],[1180,500,80,110,"#d1e2c7"],[1300,420,170,210,"#a4c5a0"],[1470,490,110,130,"#bfd6b6"],[1580,440,120,180,"#aac8a5"]] as [number, number, number, number, string][])
      .map(([cx,cy,rx,ry,f]) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="${f}"/><rect x="${cx-6}" y="${cy+ry*.6}" width="12" height="${610-cy-ry*.6}" fill="#9d9489"/>`).join("")}
    ${[180,520,860,1200,1540].map((x) => `<rect x="${x}" y="360" width="6" height="250" fill="#b7bcc2"/><ellipse cx="${x+14}" cy="362" rx="18" ry="6" fill="#fff8dc"/>`).join("")}
    ${Array.from({ length: 14 }, (_, i) => `<circle cx="${80 + i * 113}" cy="${330 + (i % 3) * 60}" r="${18 + (i % 4) * 6}" fill="#fff" opacity=".7"/>`).join("")}
    <rect y="590" width="1600" height="40" fill="#d9d3c6"/>
  </g>
  <rect y="618" width="1600" height="282" fill="url(#road)" filter="url(#asphalt)"/>
  <rect y="618" width="1600" height="10" fill="#e3dfd6"/>
  <rect y="640" width="1600" height="4" fill="#f4f4f2" opacity=".85"/>
</svg>`;
// 버스는 0.78배 — 로그인 카드 아래에 다 보이도록 (바닥선 y≈812 기준으로 줄인다)
export const MID = `<svg ${V}><g class="bob"><g transform="translate(800 812) scale(.78) translate(-800 -812)">${bus(345, 588)}</g></g></svg>`;
export const NEAR = `<svg ${V}>
  <g filter="url(#dof2)">
    <rect x="-40" y="860" width="1680" height="80" fill="#a4a8ae"/>
    ${Array.from({ length: 5 }, (_, i) => `<rect x="${-60 + i * 420}" y="872" width="300" height="14" rx="4" fill="#f2f2ef" opacity=".9"/>`).join("")}
  </g>
</svg>`;
