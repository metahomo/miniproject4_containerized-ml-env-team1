/* 대시보드 사이드바 (Intent-Tasks 패턴, T019). 로그인한 뒤에만 보인다(T108) — 유효 권한이 있는 메뉴만 (G1, RBAC T107·T110). */
import { Fragment } from "react";
import { NavLink } from "react-router-dom";
import type { Perm } from "../stores/auth";

type Item = { to: string; ic: string; label: string; perm?: Perm };
/* 아이콘 글자: 짧은 한글 — 화면 번호(S0…S10)는 보이지 않게 (2026-09-30).
   메뉴는 역할이 아니라 유효 권한(권한 매트릭스 S10, T110)을 따른다 — 권한이 없는 항목·빈 구역은 보이지 않는다. */
const SECTIONS: { title: string; items: Item[] }[] = [
  { title: "기본 기능", items: [   // 2026-09-30 홈 = 버스 조회. «API 활용» 긴 문서는 운영 관리로
    { to: "/", ic: "버스", label: "버스 조회", perm: "next_vehicle" },
    { to: "/diagnose", ic: "진단", label: "현재 프레임 진단", perm: "diagnose" },
    { to: "/my/keys", ic: "키", label: "API 키", perm: "own_keys" },
  ] },
  { title: "관제", items: [
    { to: "/admin/cameras", ic: "현황", label: "카메라 현황", perm: "control_view" },
    { to: "/admin/measurements", ic: "실측", label: "후속 차량 실측 등록", perm: "measure" },
  ] },
  { title: "운영 관리", items: [
    { to: "/admin/server", ic: "서버", label: "서버 준비", perm: "admin" },
    { to: "/admin/onboarding", ic: "등록", label: "카메라 · 차량 투입 등록", perm: "admin" },
    { to: "/admin/policy", ic: "정책", label: "진단 정책 설정", perm: "admin" },
    { to: "/admin/verification", ic: "검증", label: "정확도 검증", perm: "admin" },
    { to: "/admin/demo", ic: "시연", label: "시연 준비 · 수행", perm: "admin" },
    { to: "/admin/accounts", ic: "계정", label: "계정 · 키 관리", perm: "accounts" },
    { to: "/admin/rbac", ic: "권한", label: "권한 매트릭스", perm: "accounts" },
    { to: "/api-guide", ic: "문서", label: "API 문서 (가이드·매뉴얼)", perm: "admin" },
  ] },
];

function Links({ items }: { items: Item[] }) {
  return (
    <>
      {items.map((it) => (
        <NavLink key={it.to} to={it.to} end={it.to === "/"} className={({ isActive }) => (isActive ? "active" : "")} title={it.label}>
          <span className="ic">{it.ic}</span>
          <span className="lbl">{it.label}</span>
        </NavLink>
      ))}
    </>
  );
}

export function Sidebar({ collapsed, onToggle, perms }: { collapsed: boolean; onToggle: () => void; perms: string[] }) {
  // 카메라 전원을 바꿀 수 있으면(운영 관리) «카메라 전원 관리», 보기만 하면 «카메라 현황»
  const label = (it: Item) => (it.to === "/admin/cameras" && perms.includes("admin") ? "카메라 전원 관리" : it.label);
  const sections = SECTIONS.map((sec) => ({ ...sec, items: sec.items.filter((it) => !it.perm || perms.includes(it.perm)).map((it) => ({ ...it, label: label(it) })) }))
    .filter((sec) => sec.items.length);
  return (
    <nav className="sidebar" aria-label="주 메뉴">
      <div className="brand">
        <b>대전 버스 혼잡도</b>
        <button className="toggle" onClick={onToggle} aria-label={collapsed ? "메뉴 펼치기" : "메뉴 접기"} title={collapsed ? "펼치기" : "접기"}>
          {collapsed ? "»" : "«"}
        </button>
      </div>
      {sections.map((sec) => (
        <Fragment key={sec.title}>
          <div className="group">{sec.title}</div>
          <Links items={sec.items} />
        </Fragment>
      ))}
    </nav>
  );
}
