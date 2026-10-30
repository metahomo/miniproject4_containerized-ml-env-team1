"""역할 기반 접근 제어 (RBAC, T107·T108) — 역할은 유스케이스 액터(UC_00 §4)에서 온다.

| 역할 (role)   | 유스케이스 액터                       | 얻는 방법                                         |
|---------------|---------------------------------------|---------------------------------------------------|
| user          | 본 웹서비스 이용자 · 연계 개발자       | 회원가입 → 바로 일반 사용자 (T108)                |
| integration   | 연계 시스템                           | 일반 사용자가 신청 → 운영 관리자가 승인한 API 키   |
| webservice    | 본 웹서비스 (서버 간 호출·스크립트)   | 서버 설정의 호출 키(API_KEYS) — 브라우저 빌드에 없음 |
| controller    | 관제 담당자                           | 운영 관리자가 역할 부여                           |
| admin         | 운영 관리자                           | 운영 관리자가 부여 · 최초는 관리자 키              |

사이트와 API 는 로그인(또는 승인된 키) 없이 쓸 수 없다 — 공개는 회원가입·로그인·준비 상태·API 안내뿐 (T108).
권한은 아래 표 한 곳에서 정한다(기본값). 운영 관리자는 «권한 매트릭스»(S10, `/v1/admin/rbac`)에서 역할×기능 칸을
켜고 끌 수 있고, 바꾼 칸만 `role_permission` 에 남는다 — 유효 권한 = 기본값 + 바꾼 칸. 라우터는 `auth.require_perm` 으로
유효 권한을 따른다. 잠금: 운영 관리자 열(모두 허용)과 `admin`·`accounts` 행(운영 관리자만) — 관리 권한을 스스로 잃지 않게.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

ACCOUNT_ROLES = ("admin", "controller", "user")          # 계정에 줄 수 있는 역할
ROLE_LABEL: Dict[str, str] = {
    "admin": "운영 관리자", "controller": "관제 담당자", "user": "일반 사용자",
    "integration": "연계 시스템", "webservice": "본 웹서비스",
}

# 권한 → 가진 역할. 화면·안내(/v1/auth/roles)도 이 표를 그대로 보여 준다.
PERMISSIONS: Dict[str, Dict] = {
    "diagnose":        {"label": "현재 프레임 진단 (UC1)",             "roles": ["user", "webservice", "integration", "controller", "admin"]},
    "next_vehicle":    {"label": "버스 조회·후속 차량 여유도 (UC2)",   "roles": ["user", "webservice", "integration", "controller", "admin"]},
    "reference_read":  {"label": "기준 정보 보기 (카메라·노선·정류장)", "roles": ["user", "webservice", "integration", "controller", "admin"]},
    "measure":         {"label": "후속 차량 실측 등록 (UC10)",          "roles": ["webservice", "integration", "controller", "admin"]},
    "api_guide":       {"label": "API 활용 안내 (UC15)",               "roles": ["user", "webservice", "integration", "controller", "admin"]},
    "own_keys":        {"label": "내 API 키 신청·폐기 (운영 관리자 승인 뒤 사용)", "roles": ["user", "admin"]},
    "control_view":    {"label": "관제 뷰 — 운영 지표·차단 이벤트·카메라 현황 보기 (UC3)", "roles": ["controller", "admin"]},
    "admin":           {"label": "기준 정보·정책·매핑·검증·시연·모델 관리 (UC4·6·7·8·11·12·14)", "roles": ["admin"]},
    "accounts":        {"label": "계정 역할·정지, API 키 승인·반려·폐기", "roles": ["admin"]},
}

MATRIX_ROLES = ("user", "integration", "webservice", "controller", "admin")   # 매트릭스 열 순서
LOCKED_ROLES = {"admin"}                  # 이 열은 항상 모두 허용
LOCKED_PERMISSIONS = {"admin", "accounts"}   # 이 행은 항상 운영 관리자만


def locked(perm: str, role: str) -> bool:
    return role in LOCKED_ROLES or perm in LOCKED_PERMISSIONS


def _overrides() -> Dict[tuple, bool]:
    from . import db   # 순환 import 방지
    with db.connect() as conn:
        return {(r["permission"], r["role"]): bool(r["allowed"]) for r in db.q(conn, "SELECT permission, role, allowed FROM role_permission")}


def effective() -> Dict[str, List[str]]:
    """권한 → 유효 역할 (기본값 + 운영 관리자가 바꾼 칸). 잠긴 칸은 항상 기본값."""
    ov = _overrides()
    out: Dict[str, List[str]] = {}
    for perm, v in PERMISSIONS.items():
        out[perm] = [r for r in MATRIX_ROLES
                     if (r in v["roles"] if locked(perm, r) else ov.get((perm, r), r in v["roles"]))]
    return out


def permissions_of(role: str) -> List[str]:
    """이 역할의 유효 권한 목록 — 웹 사이드바·화면 게이트가 따른다(/v1/auth/whoami·/v1/auth/me)."""
    return [perm for perm, roles in effective().items() if role in roles]


# 관제 담당자가 볼 수 있는 운영 관리자 경로(읽기만) — 나머지 /v1/admin/* 은 운영 관리자만
CONTROLLER_READ_PATHS = {
    "/v1/admin/ops-status", "/v1/admin/gate-events", "/v1/admin/quality-metrics",
    "/v1/admin/cameras", "/v1/admin/cameras/{camera_id}", "/v1/admin/camera-power",
}


@dataclass
class Principal:
    """호출 주체 — 인증 결과 하나."""
    caller_id: str                    # 집계 기록(FR-17) 의 호출 주체
    role: str                         # 위 역할 중 하나
    via: str                          # session | api_key | env_key | admin_key
    account_id: Optional[int] = None
    login_id: Optional[str] = None
    name: Optional[str] = None
    bad_admin_key: bool = False       # 관리자 키를 보냈는데 틀림 — 관리 경로에서만 403 ADMIN_INVALID

    def can(self, perm: str) -> bool:
        return self.role in effective()[perm]


def matrix() -> List[Dict]:
    eff = effective()
    return [{"permission": k, "label": v["label"], "roles": eff[k], "default_roles": [r for r in MATRIX_ROLES if r in v["roles"]],
             "locked_roles": [r for r in MATRIX_ROLES if locked(k, r)],
             "role_labels": [ROLE_LABEL[r] for r in eff[k]]} for k, v in PERMISSIONS.items()]


def save(permissions: Dict[str, List[str]], by: str) -> Dict:
    """권한 매트릭스 저장 (S10). 기본값과 같은 칸은 지우고 다른 칸만 남긴다. 잠긴 칸을 바꾸려 하면 G2 422."""
    from sqlalchemy import text

    from . import db
    from .gates import GateBlocked

    bad_perm = sorted(set(permissions) - set(PERMISSIONS))
    bad_role = sorted({r for rs in permissions.values() for r in rs} - set(MATRIX_ROLES))
    if bad_perm or bad_role:
        raise GateBlocked("G2", "RBAC_UNKNOWN", f"정의되지 않은 권한·역할: {', '.join(bad_perm + bad_role)}", "self", 422,
                          allowed_spec={"permissions": list(PERMISSIONS), "roles": list(MATRIX_ROLES)}, record=False)
    locked_cells = [f"{perm}×{ROLE_LABEL[r]}" for perm, rs in permissions.items() for r in MATRIX_ROLES
                    if locked(perm, r) and (r in rs) != (r in PERMISSIONS[perm]["roles"])]
    if locked_cells:
        raise GateBlocked("G2", "RBAC_LOCKED", "잠긴 칸은 바꿀 수 없다 — 운영 관리자 열·계정/관리 행 (" + ", ".join(locked_cells) + ")",
                          "self", 422, record=False)
    now = db.now_iso()
    with db.connect() as conn:
        for perm, rs in permissions.items():
            for r in MATRIX_ROLES:
                if locked(perm, r):
                    continue
                want = r in rs
                conn.execute(text("DELETE FROM role_permission WHERE permission = :p AND role = :r"), {"p": perm, "r": r})
                if want != (r in PERMISSIONS[perm]["roles"]):
                    db.insert(conn, "role_permission", {"permission": perm, "role": r, "allowed": int(want), "updated_at": now, "updated_by": by})
    return view()


def view() -> Dict:
    """S10 화면용 — 열(역할)·행(권한)·유효 값·기본값·잠금, 마지막 변경."""
    from . import db
    with db.connect() as conn:
        last = db.q1(conn, "SELECT updated_at, updated_by FROM role_permission ORDER BY updated_at DESC LIMIT 1")
        n = db.q1(conn, "SELECT COUNT(*) AS n FROM role_permission")["n"]
    return {"roles": [{"role": r, "label": ROLE_LABEL[r], "locked": r in LOCKED_ROLES} for r in MATRIX_ROLES],
            "permissions": matrix(), "changed_cells": int(n),
            "updated_at": (last or {}).get("updated_at"), "updated_by": (last or {}).get("updated_by")}
