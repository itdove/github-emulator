"""Actions runner management endpoints -- registration tokens, runner CRUD."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import AuthUser, DbSession, get_repo_or_404
from app.config import settings
from app.models.actions import Runner, RegistrationToken
from app.schemas.user import _fmt_dt

router = APIRouter(tags=["actions-runners"])

BASE = settings.BASE_URL


@router.post("/repos/{owner}/{repo}/actions/runners/registration-token")
async def create_registration_token(
    owner: str, repo: str, db: DbSession, user: AuthUser,
):
    """Create a registration token for a self-hosted runner."""
    repository = await get_repo_or_404(owner, repo, db)

    token = f"AAAAAA{secrets.token_urlsafe(27)}"
    expires = datetime.now(timezone.utc) + timedelta(hours=1)

    reg = RegistrationToken(
        token=token,
        repo_id=repository.id,
        expires_at=expires,
    )
    db.add(reg)
    await db.commit()

    return {"token": token, "expires_at": _fmt_dt(expires)}


@router.post("/repos/{owner}/{repo}/actions/runners/remove-token")
async def create_remove_token(
    owner: str, repo: str, db: DbSession, user: AuthUser,
):
    """Create a remove token for a self-hosted runner."""
    token = f"AAAAAA{secrets.token_urlsafe(27)}"
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    return {"token": token, "expires_at": _fmt_dt(expires)}


@router.get("/repos/{owner}/{repo}/actions/runners")
async def list_runners(
    owner: str, repo: str, db: DbSession, user: AuthUser,
):
    """List self-hosted runners for a repository."""
    repository = await get_repo_or_404(owner, repo, db)
    result = await db.execute(
        select(Runner).where(Runner.repo_id == repository.id)
    )
    runners = result.scalars().all()
    api = f"{BASE}/api/v3"
    items = []
    for r in runners:
        items.append({
            "id": r.id,
            "name": r.name,
            "os": r.os,
            "status": r.status,
            "busy": r.busy,
            "labels": [{"id": i, "name": lbl, "type": "custom"} for i, lbl in enumerate(r.labels or [])],
        })
    return {"total_count": len(items), "runners": items}


@router.get("/repos/{owner}/{repo}/actions/runners/downloads")
async def list_runner_downloads(
    owner: str, repo: str, db: DbSession, user: AuthUser,
):
    """List runner application downloads."""
    return [
        {
            "os": "linux",
            "architecture": "x64",
            "download_url": "https://github.com/actions/runner/releases/latest",
            "filename": "actions-runner-linux-x64.tar.gz",
        },
    ]


@router.get("/repos/{owner}/{repo}/actions/runners/{runner_id}")
async def get_runner(
    owner: str, repo: str, runner_id: int, db: DbSession, user: AuthUser,
):
    """Get a self-hosted runner."""
    repository = await get_repo_or_404(owner, repo, db)
    result = await db.execute(
        select(Runner).where(Runner.id == runner_id, Runner.repo_id == repository.id)
    )
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return {
        "id": r.id,
        "name": r.name,
        "os": r.os,
        "status": r.status,
        "busy": r.busy,
        "labels": [{"id": i, "name": lbl, "type": "custom"} for i, lbl in enumerate(r.labels or [])],
    }


@router.delete("/repos/{owner}/{repo}/actions/runners/{runner_id}", status_code=204)
async def delete_runner(
    owner: str, repo: str, runner_id: int, db: DbSession, user: AuthUser,
):
    """Delete a self-hosted runner."""
    repository = await get_repo_or_404(owner, repo, db)
    result = await db.execute(
        select(Runner).where(Runner.id == runner_id, Runner.repo_id == repository.id)
    )
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Not Found")
    await db.delete(r)
    await db.commit()
