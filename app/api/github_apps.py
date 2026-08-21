"""GitHub App API endpoints — JWT-authenticated app and installation management."""

from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.config import settings
from app.models.github_app import GitHubApp
from app.services import github_app_service

router = APIRouter(tags=["github-apps"])

BASE = settings.BASE_URL


async def get_app_from_jwt(
    request: Request,
    db: DbSession,
) -> GitHubApp:
    """Dependency: authenticate via JWT and return the GitHubApp."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Requires authentication")

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Requires authentication")

    app = await github_app_service.validate_jwt(db, parts[1])
    if app is None:
        raise HTTPException(status_code=401, detail="A JSON web token could not be decoded")
    return app


@router.get("/app")
async def get_authenticated_app(
    app: GitHubApp = Depends(get_app_from_jwt),
):
    """Get the authenticated GitHub App."""
    api = f"{BASE}/api/v3"
    return {
        "id": app.id,
        "slug": app.slug,
        "node_id": f"A_{app.id}",
        "owner": {"login": app.owner, "type": "Organization"},
        "name": app.name,
        "client_id": app.client_id,
        "description": None,
        "external_url": f"{BASE}/apps/{app.slug}",
        "html_url": f"{BASE}/apps/{app.slug}",
        "created_at": app.created_at.isoformat() + "Z" if app.created_at else None,
        "updated_at": app.created_at.isoformat() + "Z" if app.created_at else None,
        "permissions": {},
        "events": [],
        "installations_count": len(app.installations) if app.installations else 0,
    }


@router.get("/app/installations")
async def list_app_installations(
    app: GitHubApp = Depends(get_app_from_jwt),
    db: DbSession = None,
):
    """List installations for the authenticated app."""
    installations = await github_app_service.list_installations(db, app.id)
    return [
        {
            "id": inst.id,
            "app_id": inst.app_id,
            "app_slug": app.slug,
            "target_type": "User" if inst.repo else "Organization",
            "account": {"login": inst.owner, "type": "Organization"},
            "repository_selection": "selected" if inst.repo else "all",
            "access_tokens_url": f"{BASE}/api/v3/app/installations/{inst.id}/access_tokens",
            "html_url": f"{BASE}/organizations/{inst.owner}/settings/installations/{inst.id}",
            "created_at": inst.created_at.isoformat() + "Z" if inst.created_at else None,
            "updated_at": inst.created_at.isoformat() + "Z" if inst.created_at else None,
            "permissions": {},
            "events": [],
        }
        for inst in installations
    ]


@router.post("/app/installations/{installation_id}/access_tokens", status_code=201)
async def create_installation_access_token(
    installation_id: int,
    app: GitHubApp = Depends(get_app_from_jwt),
    db: DbSession = None,
):
    """Create an installation access token."""
    installation = await github_app_service.get_installation(db, installation_id)
    if installation is None or installation.app_id != app.id:
        raise HTTPException(status_code=404, detail="Not Found")

    result = await github_app_service.create_installation_token(db, installation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")

    raw_token, token_obj = result
    return {
        "token": raw_token,
        "expires_at": token_obj.expires_at.replace(tzinfo=timezone.utc).isoformat(),
        "permissions": {},
        "repository_selection": "selected" if installation.repo else "all",
    }
