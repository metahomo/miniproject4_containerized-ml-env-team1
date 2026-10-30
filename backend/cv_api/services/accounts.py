"""계정·세션·API 키 (RBAC, T107·T108).

- 회원가입하면 바로 일반 사용자(user, active) — 로그인해서 사이트 기본 기능을 쓴다.
- 로그인(아이디·비밀번호) → Bearer 토큰(12시간). 토큰·키·비밀번호는 해시만 저장한다(원문은 발급 순간 한 번만 준다).
- API 키는 일반 사용자가 연계 시스템마다 신청한다(`cvk_` 로 시작). 원문은 신청 응답에서 한 번만 주고,
  운영 관리자가 승인(status='active')해야 호출에 쓰인다. 반려·폐기·계정 정지면 거부된다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from .. import db
from ..gates import GateBlocked
from ..rbac import ACCOUNT_ROLES

SESSION_HOURS = 12
KEY_PREFIX = "cvk_"
LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


# ---------------------------------------------------------------- 해시
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2 ** 14, 8, 1
    h = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:  # noqa: BLE001
        return False


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plus_hours(h: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S")


def _bad(code: str, why: str, status: int = 422, field: Optional[str] = None) -> GateBlocked:
    return GateBlocked("G8" if status == 422 else "G1", code, why, "self", status,
                       details=[{"field": field, "reason": why}] if field else None, record=False)


def public(a: Dict[str, Any]) -> Dict[str, Any]:
    """비밀번호 해시를 뺀 계정 정보."""
    return {k: (db.iso(v) if k.endswith("_at") else v) for k, v in a.items() if k != "password_hash"}


# ---------------------------------------------------------------- 계정
def _validate(login_id: str, name: str, password: str) -> None:
    if not LOGIN_RE.match(login_id or ""):
        raise _bad("LOGIN_ID_INVALID", "아이디는 영문 소문자·숫자로 시작하는 3~40자(소문자·숫자·. _ -)", field="login_id")
    if not (name or "").strip():
        raise _bad("NAME_REQUIRED", "이름을 입력한다", field="name")
    if len(password or "") < 8:
        raise _bad("PASSWORD_TOO_SHORT", "비밀번호는 8자 이상", field="password")


def create_account(body: Dict[str, Any], *, role: str, status: str, by: Optional[str] = None) -> Dict[str, Any]:
    login_id = (body.get("login_id") or "").strip().lower()
    _validate(login_id, body.get("name", ""), body.get("password", ""))
    if role not in ACCOUNT_ROLES:
        raise _bad("ROLE_INVALID", f"역할은 {', '.join(ACCOUNT_ROLES)} 중 하나", field="role")
    now = db.now_iso()
    try:
        with db.connect() as conn:
            aid = db.insert(conn, "account", {
                "login_id": login_id, "name": body["name"].strip(), "org": (body.get("org") or None), "email": (body.get("email") or None),
                "password_hash": hash_password(body["password"]), "role": role, "status": status, "created_at": now,
                "approved_at": now if status == "active" else None, "approved_by": by if status == "active" else None, "last_login_at": None,
            })
            _log_change(conn, aid, {"role": (None, role), "status": (None, status)}, by or "system", now)
            return public(db.q1(conn, "SELECT * FROM account WHERE account_id=:a", a=aid))
    except IntegrityError:
        raise _bad("LOGIN_ID_TAKEN", f"이미 쓰는 아이디다: {login_id}", field="login_id") from None


def signup(body: Dict[str, Any]) -> Dict[str, Any]:
    """회원가입 — 바로 일반 사용자로 로그인할 수 있다 (T108)."""
    return create_account(body, role="user", status="active", by="signup")


def list_accounts(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with db.connect() as conn:
        rows = db.q(conn, "SELECT a.*, (SELECT COUNT(*) FROM api_key k WHERE k.account_id=a.account_id AND k.revoked_at IS NULL AND k.status='active') AS active_keys "
                          "FROM account a" + (" WHERE a.status=:s" if status else "") + " ORDER BY a.created_at DESC", **({"s": status} if status else {}))
    return [public(r) for r in rows]


def _log_change(conn, account_id: int, diffs: Dict[str, Any], by: str, at: str) -> None:
    """역할·상태가 실제로 바뀐 것만 account_change 에 남긴다 (2026-09-30 — 누가 언제 관리자 권한을 줬는지)."""
    for field, (old, new) in diffs.items():
        db.insert(conn, "account_change", {"account_id": account_id, "field": field, "old_value": old, "new_value": new,
                                           "changed_at": at, "changed_by": by})


def account_changes(account_id: int) -> List[Dict[str, Any]]:
    with db.connect() as conn:
        _get(conn, account_id)
        return db.q(conn, "SELECT change_id, field, old_value, new_value, changed_at, changed_by FROM account_change "
                          "WHERE account_id=:a ORDER BY changed_at DESC, change_id DESC", a=account_id)


def _get(conn, account_id: int) -> Dict[str, Any]:
    a = db.q1(conn, "SELECT * FROM account WHERE account_id=:a", a=account_id)
    if not a:
        raise GateBlocked("G3", "ACCOUNT_NOT_FOUND", f"계정이 없다: {account_id}", "self", 404, record=False)
    return a


def update_account(account_id: int, changes: Dict[str, Any], by: str) -> Dict[str, Any]:
    """운영 관리자: 승인(status=active)·정지(disabled)·역할 변경. 정지하면 세션을 끊는다(키는 남지만 거부된다)."""
    with db.connect() as conn:
        a = _get(conn, account_id)
        vals: Dict[str, Any] = {}
        if changes.get("role") is not None:
            if changes["role"] not in ACCOUNT_ROLES:
                raise _bad("ROLE_INVALID", f"역할은 {', '.join(ACCOUNT_ROLES)} 중 하나", field="role")
            vals["role"] = changes["role"]
        if changes.get("status") is not None:
            if changes["status"] not in ("pending", "active", "disabled"):
                raise _bad("STATUS_INVALID", "상태는 pending·active·disabled", field="status")
            vals["status"] = changes["status"]
            if changes["status"] == "active" and a["status"] != "active":
                vals.update(approved_at=db.now_iso(), approved_by=by)
        if vals:
            db.update(conn, "account", "account_id=:a", vals, a=account_id)
            _log_change(conn, account_id, {f: (a[f], vals[f]) for f in ("role", "status") if f in vals and vals[f] != a[f]}, by, db.now_iso())
        if vals.get("status") == "disabled" or "role" in vals:
            db.update(conn, "auth_session", "account_id=:a AND revoked_at IS NULL", {"revoked_at": db.now_iso()}, a=account_id)
        return public(_get(conn, account_id))


# ---------------------------------------------------------------- 로그인·세션
def login(login_id: str, password: str) -> Dict[str, Any]:
    with db.connect() as conn:
        a = db.q1(conn, "SELECT * FROM account WHERE login_id=:l", l=(login_id or "").strip().lower())
        if not a or not check_password(password or "", a["password_hash"]):
            raise GateBlocked("G1", "LOGIN_FAILED", "아이디 또는 비밀번호가 맞지 않는다", "self", 401, record=False)
        if a["status"] == "pending":
            raise GateBlocked("G1", "ACCOUNT_PENDING", "가입 승인 대기 중이다 — 운영 관리자가 승인하면 로그인할 수 있다", "operator", 403, record=False)
        if a["status"] != "active":
            raise GateBlocked("G1", "ACCOUNT_DISABLED", "정지된 계정이다 — 운영 관리자에게 문의", "operator", 403, record=False)
        token = secrets.token_urlsafe(32)
        now, exp = db.now_iso(), _plus_hours(SESSION_HOURS)
        db.insert(conn, "auth_session", {"account_id": a["account_id"], "token_hash": sha256(token), "created_at": now, "expires_at": exp, "revoked_at": None})
        db.update(conn, "account", "account_id=:a", {"last_login_at": now}, a=a["account_id"])
        return {"token": token, "expires_at": exp, "account": public(_get(conn, a["account_id"]))}


def session_account(token: str) -> Optional[Dict[str, Any]]:
    with db.connect() as conn:
        r = db.q1(conn, "SELECT a.*, s.expires_at AS session_expires_at, s.revoked_at AS session_revoked_at FROM auth_session s "
                        "JOIN account a ON a.account_id = s.account_id WHERE s.token_hash=:h", h=sha256(token))
    if not r or r["session_revoked_at"] or db.iso(r["session_expires_at"]) <= db.now_iso() or r["status"] != "active":
        return None
    return r


def logout(token: str) -> None:
    with db.connect() as conn:
        db.update(conn, "auth_session", "token_hash=:h AND revoked_at IS NULL", {"revoked_at": db.now_iso()}, h=sha256(token))


# ---------------------------------------------------------------- API 키
def issue_key(account_id: int, name: str, *, approved_by: Optional[str] = None) -> Dict[str, Any]:
    """API 키 신청 — 원문은 이 응답에서 한 번만. 운영 관리자 승인 전(status='pending')에는 호출이 거부된다.
    운영 관리자 본인의 신청(approved_by 지정)은 바로 승인된다."""
    name = (name or "").strip()
    if not name or len(name) > 40:
        raise _bad("KEY_NAME_INVALID", "키 이름(연계 시스템 이름)은 1~40자", field="name")
    raw = KEY_PREFIX + secrets.token_urlsafe(24)
    with db.connect() as conn:
        a = _get(conn, account_id)
        if a["status"] != "active":
            raise GateBlocked("G1", "ACCOUNT_DISABLED", "사용 중인 계정만 키를 신청한다", "operator", 403, record=False)
        now = db.now_iso()
        kid = db.insert(conn, "api_key", {"account_id": account_id, "name": name, "key_prefix": raw[:10], "key_hash": sha256(raw),
                                           "created_at": now, "last_used_at": None, "revoked_at": None, "revoked_by": None,
                                           "status": "active" if approved_by else "pending",
                                           "approved_at": now if approved_by else None, "approved_by": approved_by})
        row = db.q1(conn, "SELECT * FROM api_key WHERE key_id=:k", k=kid)
    return {**_key_out(row), "key": raw}


def _key_out(r: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (db.iso(v) if k.endswith("_at") else v) for k, v in r.items() if k != "key_hash"}


def list_keys(account_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    where, args = [], {}
    if account_id:
        where.append("k.account_id=:a"); args["a"] = account_id
    if status:
        where.append("k.status=:s AND k.revoked_at IS NULL"); args["s"] = status
    with db.connect() as conn:
        rows = db.q(conn, "SELECT k.*, a.login_id, a.name AS account_name, a.org FROM api_key k JOIN account a ON a.account_id=k.account_id"
                          + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY k.created_at DESC", **args)
    return [_key_out(r) for r in rows]


def review_key(key_id: int, status: str, by: str) -> Dict[str, Any]:
    """운영 관리자: API 키 승인(active)·반려(rejected). 폐기된 키는 바꿀 수 없다."""
    if status not in ("active", "rejected"):
        raise _bad("STATUS_INVALID", "상태는 active(승인)·rejected(반려)", field="status")
    with db.connect() as conn:
        k = db.q1(conn, "SELECT * FROM api_key WHERE key_id=:k", k=key_id)
        if not k:
            raise GateBlocked("G3", "KEY_NOT_FOUND", f"키가 없다: {key_id}", "self", 404, record=False)
        if k["revoked_at"]:
            raise GateBlocked("G4", "KEY_REVOKED", "폐기된 키는 승인·반려할 수 없다", "self", 409, record=False)
        db.update(conn, "api_key", "key_id=:k", {"status": status, "approved_at": db.now_iso(), "approved_by": by}, k=key_id)
        row = db.q1(conn, "SELECT k.*, a.login_id, a.name AS account_name, a.org FROM api_key k JOIN account a ON a.account_id=k.account_id WHERE k.key_id=:k", k=key_id)
    return _key_out(row)


def revoke_key(key_id: int, by: str, owner_account_id: Optional[int] = None) -> None:
    with db.connect() as conn:
        k = db.q1(conn, "SELECT * FROM api_key WHERE key_id=:k", k=key_id)
        if not k or (owner_account_id is not None and int(k["account_id"]) != owner_account_id):
            raise GateBlocked("G3", "KEY_NOT_FOUND", f"키가 없다: {key_id}", "self", 404, record=False)
        if not k["revoked_at"]:
            db.update(conn, "api_key", "key_id=:k", {"revoked_at": db.now_iso(), "revoked_by": by}, k=key_id)


def key_principal(raw: str) -> Optional[Dict[str, Any]]:
    """API 키 → (키, 계정). 승인 전·반려·폐기된 키, 정지 계정이면 None. 마지막 사용 시각을 남긴다."""
    if not raw.startswith(KEY_PREFIX):
        return None
    with db.connect() as conn:
        r = db.q1(conn, "SELECT k.key_id, k.name, k.revoked_at, k.status AS key_status, a.account_id, a.login_id, a.status FROM api_key k "
                        "JOIN account a ON a.account_id=k.account_id WHERE k.key_hash=:h", h=sha256(raw))
        if not r or r["revoked_at"] or r["status"] != "active":
            return None
        if r["key_status"] == "pending":
            raise GateBlocked("G1", "KEY_PENDING", "승인 대기 중인 API 키다 — 운영 관리자가 승인하면 쓸 수 있다", "operator", 403)
        if r["key_status"] != "active":
            raise GateBlocked("G1", "KEY_REJECTED", "반려된 API 키다 — 새로 신청한다", "self", 403)
        db.update(conn, "api_key", "key_id=:k", {"last_used_at": db.now_iso()}, k=r["key_id"])
    return r
