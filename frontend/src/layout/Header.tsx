/* 상단 헤더 — 브레드크럼, 준비 칩(C5), 시연 칩, 정류장·카메라 검색 */
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AdminLoginChip } from "../components/AdminLogin";
import { ReadinessChip } from "../components/ReadinessChip";
import { useDemo } from "../stores/demo";
import { stopWebcam, useWebcam } from "../stores/webcam";
import { fmtTime, hhmm } from "../api/client";

const TITLES: Record<string, string> = {
  "/": "버스 조회", "/diagnose": "현재 프레임 진단", "/admin/measurements": "후속 차량 실측 등록",
  "/api-guide": "API 문서", "/admin/server": "서버 준비", "/admin/onboarding": "카메라 · 차량 투입 등록", "/admin/cameras": "카메라 전원 관리",
  "/admin/policy": "진단 정책 설정", "/admin/verification": "정확도 검증", "/admin/demo": "시연 준비 · 수행",
  "/admin/accounts": "계정 · 키 관리", "/signup": "회원가입", "/my/keys": "API 키",
};

export function Header() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const demo = useDemo();
  const cam = useWebcam();   // 노트북 카메라가 켜져 있으면 어느 화면에서든 보이고 끌 수 있다
  const [q, setQ] = useState("");
  const section = pathname.startsWith("/admin") || pathname === "/api-guide" ? "운영 관리자" : "기본 기능";
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const v = q.trim();
    if (!v) return;
    // T099: 이용자는 정류장 이름으로 찾는다 (카메라 ID 는 보내는 쪽 — 그대로 S5 로). 번호판 분기는 2026-09-30 삭제
    if (/^cam-/i.test(v)) nav(`/diagnose?camera_id=${encodeURIComponent(v)}`);
    else nav(`/?q=${encodeURIComponent(v)}`);
  };
  return (
    <header className="header">
      <div className="crumbs t-caption">
        <span>{section}</span><span>›</span><b>{TITLES[pathname] ?? "—"}</b>
      </div>
      <form className="row" onSubmit={submit} role="search">
        <input className="input" style={{ minHeight: 36, width: 220, padding: "6px 12px" }} placeholder="정류장 이름" value={q} onChange={(e) => setQ(e.target.value)} aria-label="검색" />
      </form>
      <div className="chips">
        {cam.stream && (
          <span className="chip webcam-chip" title={cam.stopped ? `진단 중지 — ${cam.stopped}` : `${cam.interval}초마다 진단 중`}>
            <span className="dot" aria-hidden />
            <button type="button" className="linklike" onClick={() => nav("/diagnose")} style={{ background: "none", border: 0, padding: 0, cursor: "pointer", font: "inherit", color: "inherit" }}>
              카메라 촬영 중{cam.cameraId ? ` · ${cam.cameraId}` : ""}{cam.stopped ? " · 진단 중지" : ""}
            </button>
            <button type="button" onClick={stopWebcam} aria-label="노트북 카메라 끄기" style={{ background: "none", border: 0, padding: "0 2px", cursor: "pointer", font: "inherit", fontWeight: 700 }}>끄기</button>
          </span>
        )}
        <ReadinessChip />
        {demo.known && (
          <span className="chip" title={demo.on ? `종료 예정 ${fmtTime(demo.endAt)}` : "시연 모드 꺼짐"}>
            시연: <b>{demo.on ? `켜짐${demo.endAt ? " · " + hhmm(demo.endAt) + " 종료" : ""}` : "꺼짐"}</b>
          </span>
        )}
        <AdminLoginChip />
      </div>
    </header>
  );
}
