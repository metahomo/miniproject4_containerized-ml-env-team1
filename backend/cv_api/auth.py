"""인증·인가 의존성 — research R6 / Clarifications 3차 Q4 + RBAC(T107, `rbac.py`).

호출 주체(Principal)를 아래 순서로 정한다 — 가장 강한 것 하나:
  1. `Authorization: Bearer <토큰>`  로그인 세션 → 계정 역할(admin·controller·user) — 웹 화면은 전부 이것으로 (T108)
  2. `X-Admin-Key`                    서버 설정의 관리자 키 → admin (최초 운영 관리자 — 계정 만들기 전)
  3. `X-API-Key`                      운영 관리자가 승인한 키(`cvk_…`) → integration, 서버 설정의 호출 키(서버 간·스크립트) → webservice
키·토큰은 해시로만 비교한다. 없으면 401, 틀리면 403 (G1).
"""
from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import Depends, Header, Request

from .gates import GateBlocked
from .rbac import CONTROLLER_READ_PATHS, PERMISSIONS, ROLE_LABEL, Principal
from .settings import Settings, get_settings


def _match(key: Optional[str], table: dict) -> Optional[str]:
    if not key:
        return None
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    for cid, expected in table.items():
        if expected == h:
            return cid
    return ""


def _g1(code: str, why: str, status: int, role: str = "self") -> GateBlocked:
    return GateBlocked("G1", code, why, role, status)


def get_principal(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> Principal:
    from .services import accounts   # 순환 import 방지

    if authorization and authorization.lower().startswith("bearer "):
        acc = accounts.session_account(authorization[7:].strip())
        if not acc:
            raise _g1("SESSION_INVALID", "로그인이 만료됐거나 유효하지 않다 — 다시 로그인", 401)
        return Principal(caller_id=acc["login_id"], role=acc["role"], via="session", account_id=int(acc["account_id"]),
                         login_id=acc["login_id"], name=acc["name"])
    admin = _match(x_admin_key, settings.admin_key_hashes)
    if admin:
        return Principal(caller_id=admin, role="admin", via="admin_key", login_id=admin, name="운영 관리자(관리자 키)")
    bad_admin = x_admin_key is not None and admin == ""
    if x_api_key:
        env = _match(x_api_key, settings.api_key_hashes)
        if env:
            return Principal(caller_id=env, role="webservice", via="env_key", bad_admin_key=bad_admin)
        k = accounts.key_principal(x_api_key)
        if k:
            return Principal(caller_id=f"{k['login_id']}:{k['name']}"[:40], role="integration", via="api_key",
                             account_id=int(k["account_id"]), login_id=k["login_id"], bad_admin_key=bad_admin)
    if bad_admin:
        raise _g1("ADMIN_INVALID", "유효하지 않은 관리자 키", 403, "operator")
    if x_api_key is None and x_admin_key is None:
        raise _g1("AUTH_MISSING", "호출 주체를 식별할 수 없다 — 로그인하거나, 회원가입 후 신청해 운영 관리자 승인을 받은 API 키를 X-API-Key 헤더에 넣는다", 401)
    raise _g1("AUTH_INVALID", "유효하지 않은 API 키 (폐기됐거나 계정이 정지됐을 수 있다)", 403)


def require_caller(p: Principal = Depends(get_principal)) -> str:
    """인증된 호출 주체면 누구나 (연계 시스템·본 웹서비스·로그인 계정). caller_id 를 돌려준다."""
    return p.caller_id


def require_admin(p: Principal = Depends(get_principal)) -> str:
    if p.role == "admin":
        return p.caller_id
    if p.bad_admin_key:
        raise _g1("ADMIN_INVALID", "유효하지 않은 관리자 키", 403, "operator")
    if p.via in ("env_key", "api_key"):
        raise _g1("ADMIN_REQUIRED", "운영 관리자만 접근할 수 있다 — 관리자 로그인이 필요하다", 401, "operator")
    raise _g1("ROLE_FORBIDDEN", f"운영 관리자만 할 수 있다 (지금 역할: {ROLE_LABEL.get(p.role, p.role)})", 403, "operator")


def require_admin_route(request: Request, p: Principal = Depends(get_principal)) -> str:
    """/v1/admin/* 라우터 공통 — 운영 관리자, 또는 관제 뷰 권한(control_view, 기본 관제 담당자)의 읽기 전용 경로(rbac.CONTROLLER_READ_PATHS)."""
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    if p.role != "admin" and request.method == "GET" and path in CONTROLLER_READ_PATHS and p.can("control_view"):
        return p.caller_id
    return require_admin(p)


def require_perm(perm: str):
    """권한 매트릭스(S10)의 유효 권한으로 거른다 — 칸이 꺼진 역할은 403 ROLE_FORBIDDEN. Principal 을 돌려준다."""
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        if p.can(perm):
            return p
        raise _g1("ROLE_FORBIDDEN", f"«{PERMISSIONS[perm]['label']}» 권한이 없다 (지금 역할: {ROLE_LABEL.get(p.role, p.role)}) "
                  "— 운영 관리자가 권한 매트릭스에서 허용해야 한다", 403, "operator")
    return dep


def require_perm_caller(perm: str):
    """require_perm 과 같고 caller_id 를 돌려준다 (집계 기록용)."""
    inner = require_perm(perm)

    def dep(p: Principal = Depends(inner)) -> str:
        return p.caller_id
    return dep


def require_roles(*roles: str):
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        if p.role in roles:
            return p
        raise _g1("ROLE_FORBIDDEN", f"이 기능은 {', '.join(ROLE_LABEL[r] for r in roles)} 만 쓸 수 있다", 403 if p.via == "session" else 401)
    return dep


def require_session(p: Principal = Depends(get_principal)) -> Principal:
    """로그인 계정(세션)만 — 내 정보·내 키."""
    if p.via != "session":
        raise _g1("LOGIN_REQUIRED", "로그인이 필요하다", 401)
    return p
