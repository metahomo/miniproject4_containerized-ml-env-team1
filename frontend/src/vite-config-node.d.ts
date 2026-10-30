// vite.config.ts 가 쓰는 Node 기능만 선언한다 (@types/node 미설치 — 외부 서비스 시연 partner/ 제공용, 2026-09-30).
// 브라우저 코드(src/)에서는 쓰지 않는다.
declare module "node:fs" {
  const fs: { readFileSync(path: string, encoding: "utf8"): string };
  export default fs;
}
declare module "node:path" {
  const path: { resolve(...parts: string[]): string; join(...parts: string[]): string };
  export default path;
}
declare const __dirname: string;
