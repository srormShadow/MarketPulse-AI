"""Authentication routes — login and current user info."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse
from starlette import status

from marketpulse.core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from marketpulse.core.audit import emit as audit
from marketpulse.core.config import get_settings
from marketpulse.core.login_throttle import check_lockout, record_failure, record_success
from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import require_csrf
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/auth/login", response_model=None)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: dict = Body(...),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    """Authenticate with email + password, set an HttpOnly session cookie, and return user info + CSRF token."""
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not email or not password:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Email and password are required."},
        )

    # Check account lockout before attempting verification
    locked, remaining = check_lockout(email)
    if locked:
        audit(action="login_locked", request=request, detail=f"email={email} locked_for={remaining}s", repo=repo)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"status": "error", "message": f"Account temporarily locked. Try again in {remaining} seconds."},
        )

    user = repo.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        record_failure(email)
        audit(action="login_failed", request=request, detail=f"email={email}", repo=repo)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Invalid email or password."},
        )

    token = create_access_token(
        {
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
            "tv": int(user.get("token_version", 1)),
            "organization_id": user["organization_id"],
        }
    )

    # Issue CSRF token (readable) alongside HttpOnly session cookie
    import secrets

    csrf_token = secrets.token_urlsafe(32)

    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "user": {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"],
                "organization_id": user["organization_id"],
            },
            "csrf_token": csrf_token,
        },
    )
    # HttpOnly session cookie for JWT
    response.set_cookie(
        get_settings().session_cookie_name,
        token,
        httponly=True,
        secure=get_settings().session_cookie_secure or get_settings().environment.lower() in {"production", "prod"},
        samesite="strict",
        path="/",
        max_age=60 * 60 * 8,
    )
    # Non-HttpOnly CSRF cookie
    response.set_cookie(
        "mp_csrf",
        csrf_token,
        httponly=False,
        secure=get_settings().session_cookie_secure or get_settings().environment.lower() in {"production", "prod"},
        samesite="strict",
        path="/",
        max_age=60 * 60 * 8,
    )

    record_success(email)
    logger.info("User logged in: %s (role=%s)", email, user["role"])
    audit(action="login_success", request=request, user=user, repo=repo)

    return response


@router.post("/auth/register", response_model=None)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: dict = Body(...),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    organization_name = str(payload.get("organization_name", "")).strip()

    if not email or not password or not organization_name:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Email, password, and organization name are required."},
        )
    if len(password) < 10:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Password must be at least 10 characters."},
        )
    if repo.get_user_by_email(email):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"status": "error", "message": "An account with this email already exists."},
        )

    organization = repo.create_organization(name=organization_name, plan="starter")
    user = repo.create_user(
        email=email,
        password_hash=hash_password(password),
        role="retailer",
        organization_id=organization["id"],
    )

    token = create_access_token(
        {
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
            "tv": int(user.get("token_version", 1)),
            "organization_id": user["organization_id"],
        }
    )

    import secrets

    csrf_token = secrets.token_urlsafe(32)
    response = JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "user": {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"],
                "organization_id": user["organization_id"],
            },
            "csrf_token": csrf_token,
        },
    )
    secure_cookie = get_settings().session_cookie_secure or get_settings().environment.lower() in {"production", "prod"}
    response.set_cookie(get_settings().session_cookie_name, token, httponly=True, secure=secure_cookie, samesite="strict", path="/", max_age=60 * 60 * 8)
    response.set_cookie("mp_csrf", csrf_token, httponly=False, secure=secure_cookie, samesite="strict", path="/", max_age=60 * 60 * 8)
    audit(action="register", request=request, user=user, resource=f"org={organization['id']}", repo=repo)
    return response


@router.post("/auth/logout", response_model=None)
async def logout(
    response: Response,
    current_user: dict = Depends(get_current_user),
    repo: "DataRepository" = Depends(get_repo),
    _csrf: None = Depends(require_csrf),
) -> JSONResponse:
    """Clear the session and CSRF cookies."""
    repo.bump_user_token_version(int(current_user.get("id") or current_user.get("sub", 0)))
    audit(action="logout", user=current_user, repo=repo)
    resp = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok"},
    )
    resp.delete_cookie(get_settings().session_cookie_name, path="/")
    resp.delete_cookie("mp_csrf", path="/")
    return resp


@router.get("/auth/me", response_model=None)
async def get_me(
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Return the current authenticated user's info from the JWT."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "id": int(current_user.get("id") or current_user.get("sub", 0)),
            "email": current_user.get("email", ""),
            "role": current_user.get("role", ""),
            "organization_id": current_user.get("organization_id"),
        },
    )
