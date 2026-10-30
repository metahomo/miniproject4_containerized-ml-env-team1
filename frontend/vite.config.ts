/// <reference types="vitest" />
import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// ---- 외부 서비스 시연: 영상 혼잡도 측정 (2026-09-30) -------------------------------------------------
// 페이지 https://p4.sumzip.com/partner/ = 프로젝트 루트 partner/ 폴더 (본 웹과 별개 코드).
// 브라우저는 영상 파일·카메라에서 프레임을 떠 /partner-api/v1/diagnose 로만 보낸다. 이 서버(외부 서비스의 백엔드 역할)가
// 승인된 API 키(partner/.secrets, 권한 600)를 붙여 공개 게이트웨이 https://p4.sumzip.com/model-api 로 넘긴다 — 키는 브라우저에 가지 않는다.
// 이 서비스 전용 카메라(CAM-PARTNER-01) 외의 진단은 중계하지 않는다.
const PARTNER_DIR = path.resolve(__dirname, "../partner");
const PARTNER_GATEWAY = "https://p4.sumzip.com/model-api";
const PARTNER_CAMERA = "CAM-PARTNER-01";
const PARTNER_MAX_BYTES = 6 * 1024 * 1024;   // 프레임 한 장 (API 한도 10 MB 보다 작게)
const PARTNER_GET = new Set(["/v1/readiness", `/v1/reference/cameras/${PARTNER_CAMERA}`]);
const PARTNER_KEY = (() => {
  try {
    return fs.readFileSync(path.join(PARTNER_DIR, ".secrets"), "utf8").match(/^API_KEY=(.+)$/m)?.[1].trim() ?? "";
  } catch {
    return "";
  }
})();

type Res = { statusCode: number; setHeader(k: string, v: string): void; end(body?: string | Uint8Array): void };
type Req = { url?: string; method?: string; headers: Record<string, string | undefined>; on(ev: string, fn: (x?: Uint8Array) => void): void };

function send(res: Res, code: number, body: string | Uint8Array, type = "application/json; charset=utf-8") {
  res.statusCode = code;
  res.setHeader("Content-Type", type);
  res.end(body);
}

function readBody(req: Req, limit: number): Promise<Uint8Array | null> {
  return new Promise((resolve) => {
    const chunks: Uint8Array[] = [];
    let size = 0;
    req.on("data", (c) => { size += c!.length; if (size <= limit) chunks.push(c!); });
    req.on("end", () => {
      if (size > limit) return resolve(null);
      const out = new Uint8Array(size); let o = 0;
      for (const c of chunks) { out.set(c, o); o += c.length; }
      resolve(out);
    });
  });
}

async function relay(req: Req, res: Res, apiPath: string) {
  const headers: Record<string, string> = { "X-API-Key": PARTNER_KEY, Accept: "application/json" };   // 브라우저가 보낸 자격 헤더는 넘기지 않는다
  let body: Uint8Array | undefined;
  if (req.method === "POST") {
    const buf = await readBody(req, PARTNER_MAX_BYTES);
    if (!buf) return send(res, 413, JSON.stringify({ reason: `프레임이 ${PARTNER_MAX_BYTES / 1048576} MB 를 넘는다` }));
    const text = new TextDecoder("latin1").decode(buf);
    const cam = /name="camera_id"\r\n\r\n([^\r]*)/.exec(text)?.[1];
    if (cam !== PARTNER_CAMERA) return send(res, 403, JSON.stringify({ reason: `이 서비스는 ${PARTNER_CAMERA} 만 진단한다` }));
    body = buf;
    headers["Content-Type"] = req.headers["content-type"] || "";
  }
  try {
    const r = await fetch(PARTNER_GATEWAY + apiPath, { method: req.method, headers, body: body ? (body.buffer as ArrayBuffer) : undefined });
    res.setHeader("X-Request-ID", r.headers.get("x-request-id") || "");
    send(res, r.status, new Uint8Array(await r.arrayBuffer()), r.headers.get("content-type") || "application/json");
  } catch {
    send(res, 502, JSON.stringify({ reason: "진단 API 게이트웨이에 연결하지 못했다" }));
  }
}

function partnerSite(): Plugin {
  return {
    name: "partner-site",
    configureServer(server) {
      server.middlewares.use((rq, rs, next) => {
        const req = rq as unknown as Req, res = rs as unknown as Res;
        const url = req.url || "";
        if (url.startsWith("/partner-api/")) {
          const apiPath = url.slice("/partner-api".length);
          const ok = (req.method === "GET" && PARTNER_GET.has(apiPath)) || (req.method === "POST" && apiPath === "/v1/diagnose");
          if (!ok) return send(res, 403, JSON.stringify({ reason: "이 서비스가 중계하지 않는 요청" }));
          if (!PARTNER_KEY) return send(res, 503, JSON.stringify({ reason: "API 키가 설정되지 않았다 (partner/.secrets)" }));
          void relay(req, res, apiPath);
          return;
        }
        if (url === "/partner") {
          res.statusCode = 301; res.setHeader("Location", "/partner/"); return res.end();
        }
        if (url === "/partner/" || url.startsWith("/partner/?") || url.startsWith("/partner/index.html")) {
          return send(res, 200, fs.readFileSync(path.join(PARTNER_DIR, "index.html"), "utf8"), "text/html; charset=utf-8");
        }
        if (url.startsWith("/partner/")) return send(res, 404, "Not Found", "text/plain; charset=utf-8");   // 점 파일(.secrets) 등은 내주지 않는다
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), partnerSite()],
  server: {
    port: 9504,   // 배정 포트 (프론트엔드)
    host: true,   // 공유 서버: 다른 PC 브라우저에서 접속 (0.0.0.0)
    allowedHosts: ["p4.sumzip.com"],   // nginx 리버스 프록시 도메인
    // VITE_API_BASE 가 비어 있으면 이 프록시로 전달한다. 백엔드는 한 프로세스가 같은 전체 앱을 9524·9544 로 연다(D1, cv_api/serve.py).
    //   웹 → 9524 (9544 는 외부 연계용 공개 포트). 경로별로 나눌 필요가 없다.
    proxy: {
      "/v1": { target: "http://localhost:9524", changeOrigin: true },
      "/docs": { target: "http://localhost:9524", changeOrigin: true },
      "/openapi.json": { target: "http://localhost:9524", changeOrigin: true },
      // 공개 API 산출물 https://p4.sumzip.com/API → 9544 (외부 연계용 FastAPI·Swagger). 접두사 /API 는 백엔드 PublicPrefix 가 처리 (T094)
      "^/API(/.*)?$": { target: "http://localhost:9544", changeOrigin: true },
      // 모델 게이트웨이 https://p4.sumzip.com/model-api → 9544 (API 점검 2026-09-30 A3). 접두는 떼지 않는다 — 앱 PublicPrefix 가 한 번만 처리
      "^/model-api(/.*)?$": { target: "http://localhost:9544", changeOrigin: true },
    },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["./tests/setup.ts"] },
});
