"""Admin routes — system-wide visibility for admin users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from starlette import status

from marketpulse.core.auth import require_admin
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

router = APIRouter(prefix="/admin")


@router.get("/users", response_model=None)
async def list_users(
    _admin: dict = Depends(require_admin),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    users = repo.list_users()
    # Strip password hashes before sending
    safe_users = [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in users
    ]
    return JSONResponse(status_code=status.HTTP_200_OK, content={"users": safe_users})


@router.get("/organizations", response_model=None)
async def list_organizations(
    _admin: dict = Depends(require_admin),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    orgs = repo.list_organizations()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"organizations": orgs})


@router.get("/stores", response_model=None)
async def list_stores(
    _admin: dict = Depends(require_admin),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    stores = repo.list_shopify_stores()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"stores": stores})


@router.get("/stats", response_model=None)
async def system_stats(
    _admin: dict = Depends(require_admin),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "total_users": repo.count_users(),
            "total_organizations": repo.count_organizations(),
            "total_stores": repo.count_shopify_stores(),
            "total_skus": repo.count_skus(),
            "total_sales": repo.count_sales(),
        },
    )
