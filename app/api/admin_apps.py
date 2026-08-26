"""Admin endpoints for GitHub App management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.api.deps import DbSession
from app.services import github_app_service

router = APIRouter(prefix="/admin/api/apps", tags=["admin-apps"])


class CreateAppRequest(BaseModel):
    name: str
    owner: str = "admin"


class CreateInstallationRequest(BaseModel):
    owner: str
    repo: Optional[str] = None


@router.post("", status_code=201)
async def create_app(body: CreateAppRequest, db: DbSession):
    """Register a new GitHub App."""
    app, private_key = await github_app_service.create_app(db, body.name, body.owner)
    return {
        "app_id": app.id,
        "name": app.name,
        "slug": app.slug,
        "owner": app.owner,
        "client_id": app.client_id,
        "private_key": private_key,
        "created_at": app.created_at.isoformat() + "Z" if app.created_at else None,
    }


@router.get("")
async def list_apps(db: DbSession):
    """List all registered GitHub Apps."""
    apps = await github_app_service.list_apps(db)
    return [
        {
            "app_id": app.id,
            "name": app.name,
            "slug": app.slug,
            "owner": app.owner,
            "client_id": app.client_id,
            "installations_count": len(app.installations) if app.installations else 0,
            "created_at": app.created_at.isoformat() + "Z" if app.created_at else None,
        }
        for app in apps
    ]


@router.get("/{app_id}")
async def get_app(app_id: int, db: DbSession):
    """Get GitHub App details."""
    app = await github_app_service.get_app(db, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return {
        "app_id": app.id,
        "name": app.name,
        "slug": app.slug,
        "owner": app.owner,
        "client_id": app.client_id,
        "installations": [
            {
                "id": inst.id,
                "owner": inst.owner,
                "repo": inst.repo,
                "created_at": inst.created_at.isoformat() + "Z" if inst.created_at else None,
            }
            for inst in (app.installations or [])
        ],
        "created_at": app.created_at.isoformat() + "Z" if app.created_at else None,
    }


@router.get("/{app_id}/private-key")
async def get_private_key(app_id: int, db: DbSession):
    """Download the private key PEM."""
    app = await github_app_service.get_app(db, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Not Found")
    if app.private_key_pem is None:
        raise HTTPException(status_code=404, detail="Private key not available")
    return {"private_key": app.private_key_pem}


@router.post("/{app_id}/private-key/regenerate")
async def regenerate_private_key(app_id: int, db: DbSession):
    """Regenerate the RSA keypair."""
    result = await github_app_service.regenerate_private_key(db, app_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Not Found")
    app, private_key = result
    return {
        "app_id": app.id,
        "private_key": private_key,
    }


@router.post("/{app_id}/installations", status_code=201)
async def create_installation(
    app_id: int, body: CreateInstallationRequest, db: DbSession
):
    """Install app on an org or repo."""
    installation = await github_app_service.create_installation(
        db, app_id, body.owner, body.repo
    )
    if installation is None:
        raise HTTPException(status_code=404, detail="App not found")
    return {
        "id": installation.id,
        "app_id": installation.app_id,
        "owner": installation.owner,
        "repo": installation.repo,
        "created_at": installation.created_at.isoformat() + "Z" if installation.created_at else None,
    }
