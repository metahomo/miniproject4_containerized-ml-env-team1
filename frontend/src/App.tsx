import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AdminGate, PermGate } from "./components/AdminLogin";
import { Header } from "./layout/Header";
import { SimpleBar } from "./layout/SimpleBar";
import { Sidebar } from "./layout/Sidebar";
import ApiGuide from "./pages/ApiGuide";
import Diagnose from "./pages/Diagnose";
import Measurement from "./pages/Measurement";
import Login, { AuthShell } from "./pages/Login";
import NextVehicle from "./pages/NextVehicle";
import Signup from "./pages/Signup";
import Accounts from "./pages/admin/Accounts";
import Keys from "./pages/my/Keys";
import Cameras from "./pages/admin/Cameras";
import Demo from "./pages/admin/Demo";
import Onboarding from "./pages/admin/Onboarding";
import Policy from "./pages/admin/Policy";
import Rbac from "./pages/admin/Rbac";
import Server from "./pages/admin/Server";
import Verification from "./pages/admin/Verification";
import { designCode, isStaff, refreshPerms, useAuth, usePerms } from "./stores/auth";

/* 옛 주소 /next-vehicle?… → 홈(버스 조회)으로, 조회 조건은 그대로 (2026-09-30 홈 = 버스 조회) */
function ToHome() {
  const { search } = useLocation();
  return <Navigate to={"/" + search} replace />;
}

export default function App() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("cv.sidebar") === "1"; } catch { return false; }
  });
  const toggle = () => {
    setCollapsed((c) => {
      try { localStorage.setItem("cv.sidebar", c ? "0" : "1"); } catch { /* ignore */ }
      return !c;
    });
  };
  const me = useAuth();   // T108: 로그인해야 사이트를 쓴다 — 로그인 전에는 로그인·회원가입 화면만
  const perms = usePerms();   // 메뉴·화면 게이트는 유효 권한(권한 매트릭스 S10)을 따른다 — 로그인·창 복귀 때 새로 받는다
  const loginId = me?.login_id;
  useEffect(() => {
    if (!loginId) return;
    refreshPerms();
    const onFocus = () => { refreshPerms(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loginId]);
  if (!me) {
    return (
      <Routes>
        <Route path="/signup" element={<AuthShell><Signup /></AuthShell>} />
        <Route path="*" element={<Login />} />   {/* 주소는 그대로 — 로그인하면 그 화면이 열린다 */}
      </Routes>
    );
  }
  /* 2026-09-30 홈 단순화: 이 사이트를 쓰는 사람은 두 부류 — 버스가 얼마나 찼는지 보려는 사람, API 를 쓰려는 사람.
     관제·운영 권한이 없는 계정은 사이드바 없이 «버스 조회(홈)» 와 «API 키» 만 본다. */
  if (!isStaff(perms)) {
    return (
      <div className="simple-shell">
        <SimpleBar />
        <main className="simple-main">
          <Routes>
            <Route path="/" element={<PermGate perm="next_vehicle"><NextVehicle /></PermGate>} />
            <Route path="/next-vehicle" element={<ToHome />} />
            <Route path="/my/keys" element={<PermGate perm="own_keys" why="API 키는 일반 사용자가 신청하고 운영 관리자가 승인한다."><Keys /></PermGate>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    );
  }
  return (
    <div className={"shell" + (collapsed ? " collapsed" : "")}>
      <Sidebar collapsed={collapsed} onToggle={toggle} perms={perms} />
      <Header />
      <main className="main">
        <Routes>
          <Route path="/" element={<PermGate perm="next_vehicle"><NextVehicle /></PermGate>} />   {/* 홈 = 버스 조회 (2026-09-30) */}
          <Route path="/diagnose" element={<PermGate perm="diagnose"><Diagnose /></PermGate>} />
          <Route path="/diagnose/control" element={<Navigate to="/diagnose" replace />} />   {/* 관제 뷰는 2026-09-30 삭제 — 판단 도구가 저장·전달되지 않았다 */}
          <Route path="/measurements" element={<Navigate to="/admin/measurements" replace />} />   {/* S6 은 운영 관리자 메뉴로 (T101) */}
          <Route path="/next-vehicle" element={<ToHome />} />
          <Route path="/api-guide" element={<PermGate perm="api_guide"><ApiGuide /></PermGate>} />   {/* 긴 API 문서는 운영 관리 메뉴에서 — 이용자는 «API 키» 의 짧은 사용법 */}
          <Route path="/signup" element={<Navigate to="/" replace />} />
          <Route path="/my/keys" element={<PermGate perm="own_keys" why="API 키는 일반 사용자가 신청하고 운영 관리자가 승인한다.">
            <Keys /></PermGate>} />
          {/* 권한 화면 — 유효 권한이 없으면 G1 차단 + 로그인 폼 (PermGate · AdminGate, 권한 매트릭스 S10) */}
          <Route path="/admin/server" element={<AdminGate><Server /></AdminGate>} />
          <Route path="/admin/onboarding" element={<AdminGate><Onboarding /></AdminGate>} />
          <Route path="/admin/cameras" element={<PermGate perm="control_view" why="카메라 현황은 관제 권한으로 본다. 전원·운영 상태 변경은 운영 관리자만."><Cameras /></PermGate>} />
          <Route path="/admin/policy" element={<AdminGate><Policy /></AdminGate>} />
          <Route path="/admin/verification" element={<AdminGate><Verification /></AdminGate>} />
          <Route path="/admin/measurements" element={<PermGate perm="measure" why={`후속 차량 실측 등록${designCode("(UC10)")}은 실측 등록 권한이 있는 역할만 — 기본값은 관제 담당자·운영 관리자.`}><Measurement /></PermGate>} />
          <Route path="/admin/demo" element={<AdminGate><Demo /></AdminGate>} />
          <Route path="/admin/accounts" element={<PermGate perm="accounts"><Accounts /></PermGate>} />
          <Route path="/admin/rbac" element={<PermGate perm="accounts"><Rbac /></PermGate>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
