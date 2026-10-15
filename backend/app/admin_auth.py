"""Authentication boundary for the single deployment-configured administrator."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AdminAuthAttempt, AdminSession


router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
ADMIN_COOKIE_NAME = "pathaid_admin_session"
ADMIN_SESSION_HOURS = 4
ADMIN_LOGIN_LIMIT = 5
ADMIN_LOGIN_WINDOW_MINUTES = 15


class AdminCredentials(BaseModel):
    """Credentials checked only against deployment-provided configuration."""

    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


def now() -> datetime:
    """Return an aware UTC timestamp for session and throttle comparisons."""

    return datetime.now(timezone.utc)


def digest(value: str) -> str:
    """Hash session, CSRF, and address values before database storage."""

    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(password: str, stored: str) -> bool:
    """Verify the encoded scrypt hash supplied through deployment secrets."""

    try:
        _, n, r, p, salt, expected = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def check_admin_origin(request: Request) -> None:
    """Reject mutations sent from an unexpected browser origin."""

    allowed = os.environ.get("PATHAID_PUBLIC_ORIGIN")
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (origin and allowed and origin != allowed):
        raise HTTPException(403, detail="Origin not allowed")


def _address_key(request: Request) -> str:
    """Use only the direct peer address because forwarding headers are untrusted."""

    return digest(request.client.host if request.client else "unknown")


def _check_rate_limit(db: Session, request: Request) -> None:
    """Limit repeated admin authentication attempts across server processes."""

    cutoff = now() - timedelta(minutes=ADMIN_LOGIN_WINDOW_MINUTES)
    attempts = db.scalar(
        select(func.count()).select_from(AdminAuthAttempt).where(
            AdminAuthAttempt.address == _address_key(request),
            AdminAuthAttempt.created_at >= cutoff,
        )
    )
    if attempts >= ADMIN_LOGIN_LIMIT:
        raise HTTPException(429, detail="Too many authentication attempts")


def _record_attempt(db: Session, request: Request) -> None:
    """Record an attempt and remove expired entries for the same address."""

    cutoff = now() - timedelta(minutes=ADMIN_LOGIN_WINDOW_MINUTES)
    address = _address_key(request)
    db.execute(delete(AdminAuthAttempt).where(AdminAuthAttempt.address == address, AdminAuthAttempt.created_at < cutoff))
    db.add(AdminAuthAttempt(address=address, created_at=now()))
    db.commit()


def current_admin(request: Request, db: Session = Depends(get_db)) -> AdminSession:
    """Resolve an opaque cookie to a current server-side admin session."""

    token = request.cookies.get(ADMIN_COOKIE_NAME)
    session = db.get(AdminSession, digest(token)) if token else None
    expiry = session.expires_at if session else None
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if session is None or expiry <= now():
        raise HTTPException(401, detail="Administrator authentication required")
    return session


def require_admin_csrf(
    request: Request,
    session: AdminSession = Depends(current_admin),
) -> AdminSession:
    """Require expected origin and the session's current CSRF token."""

    check_admin_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(digest(supplied), session.csrf_hash):
        raise HTTPException(403, detail="CSRF token required")
    return session


@router.post("/login")
def admin_login(body: AdminCredentials, request: Request, response: Response, db: Session = Depends(get_db)):
    """Verify deployment credentials and issue a revocable admin session."""

    check_admin_origin(request)
    _check_rate_limit(db, request)
    configured_email = os.environ.get("PATHAID_ADMIN_EMAIL", "").strip().casefold()
    configured_hash = os.environ.get("PATHAID_ADMIN_PASSWORD_HASH", "").strip()
    if not configured_email or not configured_hash:
        raise HTTPException(503, detail="Administrator authentication is not configured")
    email_matches = hmac.compare_digest(body.email.strip().casefold(), configured_email)
    password_matches = verify_password(body.password, configured_hash)
    _record_attempt(db, request)
    if not email_matches or not password_matches:
        raise HTTPException(401, detail="Invalid credentials")

    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    session = AdminSession(
        token_hash=digest(token),
        admin_email=configured_email,
        csrf_hash=digest(csrf),
        expires_at=now() + timedelta(hours=ADMIN_SESSION_HOURS),
    )
    db.add(session)
    db.commit()
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        token,
        max_age=ADMIN_SESSION_HOURS * 3600,
        httponly=True,
        secure=os.environ.get("PATHAID_SECURE_COOKIES", "false").lower() == "true",
        samesite="lax",
        path="/api/admin",
    )
    return {"email": configured_email, "authenticated": True, "csrf_token": csrf}


@router.get("/session")
def admin_session_info(
    request: Request,
    session: AdminSession = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Confirm login and rotate the CSRF token after an admin page reload."""

    check_admin_origin(request)
    csrf = secrets.token_urlsafe(32)
    session.csrf_hash = digest(csrf)
    db.commit()
    return {"email": session.admin_email, "authenticated": True, "csrf_token": csrf}


@router.post("/logout", status_code=204)
def admin_logout(
    response: Response,
    session: AdminSession = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
):
    """Revoke the server-side admin session and clear its browser cookie."""

    db.delete(session)
    db.commit()
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/api/admin")
