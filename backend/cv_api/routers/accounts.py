"""회원가입·로그인·내 API 키 (/v1/auth/*) 와 계정·키 관리 (/v1/admin/accounts·api-keys) — RBAC, T107·T108.

사이트는 로그인해야 쓴다. 회원가입하면 바로 일반 사용자.
API 서비스를 쓰려면: 로그인 → «내 API 키»에서 연계 시스템용 키 신청(원문은 이때 한 번만) → 운영 관리자 승인 → X-API-Key 로 호출.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Response

from ..auth import require_admin, require_perm, require_session
from .. import rbac
from ..rbac import ROLE_LABEL, Principal, matrix, permissions_of
from ..schemas import AccountCreate, AccountUpdate, KeyCreate, KeyReview, LoginRequest, RbacUpdate, SignupRequest
from ..services import accounts

auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])
admin_router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------- 공개 (키 없이)
@auth_router.post("/signup", status_code=201, summary="회원가입 — 바로 일반 사용자로 로그인 (API 키는 따로 신청 → 운영 관리자 승인)")
def signup(body: SignupRequest) -> dict:
    a = accounts.signup(body.model_dump())
    return {"account": a, "message": "가입했다. 바로 로그인할 수 있다. API 키는 로그인 후 «내 API 키»에서 신청하고, 운영 관리자가 승인하면 쓸 수 있다."}


@auth_router.post("/login", summary="로그인 — Bearer 토큰(12시간) 발급")
def login(body: LoginRequest) -> dict:
    return accounts.login(body.login_id, body.password)


@auth_router.get("/roles", summary="역할·권한 표 (RBAC) — 유스케이스 액터 기준")
def roles() -> dict:
    return {"roles": ROLE_LABEL, "permissions": matrix()}


# ---------------------------------------------------------------- 로그인 계정
@auth_router.post("/logout", status_code=204, summary="로그아웃 — 세션 토큰 폐기")
def logout(authorization: Optional[str] = Header(default=None, alias="Authorization"), p: Principal = Depends(require_session)) -> Response:
    accounts.logout((authorization or "")[7:].strip())
    return Response(status_code=204)


@auth_router.get("/me", summary="내 계정 (로그인 세션)")
def me(p: Principal = Depends(require_session)) -> dict:
    return {"login_id": p.login_id, "name": p.name, "role": p.role, "role_label": ROLE_LABEL.get(p.role, p.role),
            "permissions": permissions_of(p.role)}


@auth_router.get("/keys", summary="내 API 키 목록 — 상태 pending(승인 대기)·active·rejected")
def my_keys(p: Principal = Depends(require_perm("own_keys"))) -> List[dict]:
    if p.account_id is None:
        return []
    return accounts.list_keys(p.account_id)


@auth_router.post("/keys", status_code=201, summary="API 키 신청 — 원문은 이 응답에서 한 번만, 운영 관리자 승인 뒤 사용 (연계 시스템마다 하나)")
def issue_key(body: KeyCreate, p: Principal = Depends(require_perm("own_keys"))) -> dict:
    if p.account_id is None:
        from ..gates import GateBlocked
        raise GateBlocked("G1", "LOGIN_REQUIRED", "키는 로그인한 계정으로 발급한다 (관리자 키로는 발급 불가)", "self", 401, record=False)
    return accounts.issue_key(p.account_id, body.name, approved_by=p.caller_id if p.role == "admin" else None)


@auth_router.delete("/keys/{key_id}", status_code=204, summary="내 API 키 폐기 — 즉시 거부된다")
def revoke_my_key(key_id: int, p: Principal = Depends(require_perm("own_keys"))) -> Response:
    accounts.revoke_key(key_id, p.caller_id, owner_account_id=p.account_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- 운영 관리자
@admin_router.get("/accounts", summary="계정 목록 (status 로 거르기)")
def list_accounts(status: Optional[str] = None) -> List[dict]:
    return accounts.list_accounts(status)


@admin_router.post("/accounts", status_code=201, summary="계정 만들기 (운영 관리자·관제 담당자 등 — 바로 사용 가능)")
def create_account(body: AccountCreate, admin: str = Depends(require_admin)) -> dict:
    return accounts.create_account(body.model_dump(), role=body.role, status="active", by=admin)


@admin_router.patch("/accounts/{account_id}", summary="계정 정지(disabled)·해제(active)·역할 변경")
def update_account(account_id: int, body: AccountUpdate, admin: str = Depends(require_admin)) -> dict:
    return accounts.update_account(account_id, body.model_dump(exclude_none=True), admin)


@admin_router.get("/accounts/{account_id}/changes", summary="계정 역할·상태 변경 이력 — 누가 언제 무엇을 바꿨는지 (최신 순)")
def account_changes(account_id: int) -> List[dict]:
    return accounts.account_changes(account_id)


@admin_router.get("/api-keys", summary="API 키 전체 (원문 없음 — 앞자리·소유자·상태·마지막 사용). status=pending 이면 승인 대기")
def all_keys(status: Optional[str] = None) -> List[dict]:
    return accounts.list_keys(status=status)


@admin_router.patch("/api-keys/{key_id}", summary="API 키 승인(status=active)·반려(rejected)")
def review_key(key_id: int, body: KeyReview, admin: str = Depends(require_admin)) -> dict:
    return accounts.review_key(key_id, body.status, admin)


@admin_router.delete("/api-keys/{key_id}", status_code=204, summary="API 키 폐기 (운영 관리자)")
def revoke_key(key_id: int, admin: str = Depends(require_admin)) -> Response:
    accounts.revoke_key(key_id, admin)
    return Response(status_code=204)



@admin_router.get("/rbac", summary="권한 매트릭스 (S10) — 역할×기능 유효 권한·기본값·잠긴 칸, 마지막 변경")
def rbac_view() -> dict:
    return rbac.view()


@admin_router.put("/rbac", summary="권한 매트릭스 저장 (S10) — 권한마다 허용 역할 전체. 기본값과 다른 칸만 남는다. 잠긴 칸(운영 관리자 열·계정/관리 행)은 422")
def rbac_save(body: RbacUpdate, admin: str = Depends(require_admin)) -> dict:
    return rbac.save(body.permissions, admin)
