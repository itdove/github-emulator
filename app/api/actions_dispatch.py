"""Custom runner job dispatch protocol -- long-poll, progress, completion."""

import asyncio
import hashlib
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DbSession, get_repo_or_404
from app.config import settings
from app.models.actions import Runner, RegistrationToken, WorkflowJob, WorkflowRun
from app.services.auth_service import hash_token
from app.services.workflow_service import check_run_completion, dispatch_ready_jobs

router = APIRouter(tags=["actions-dispatch"])


async def _get_runner_from_token(request: Request, db) -> Runner:
    """Authenticate a runner by its bearer token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Runner token required")
    token = auth[7:]
    token_hash = hash_token(token)
    result = await db.execute(
        select(Runner).where(Runner.token_hash == token_hash)
    )
    runner = result.scalar_one_or_none()
    if runner is None:
        raise HTTPException(status_code=401, detail="Invalid runner token")
    return runner


@router.post("/actions/runner/register")
async def register_runner(body: dict, db: DbSession):
    """Register a new runner using a registration token."""
    reg_token = body.get("token", "")
    name = body.get("name", "unnamed-runner")
    labels = body.get("labels", ["self-hosted", "linux"])
    runner_os = body.get("os", "linux")

    result = await db.execute(
        select(RegistrationToken).where(RegistrationToken.token == reg_token)
    )
    reg = result.scalar_one_or_none()
    if reg is None:
        raise HTTPException(status_code=401, detail="Invalid registration token")

    if reg.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Registration token expired")

    import secrets
    runner_token = f"ghp_runner_{secrets.token_urlsafe(32)}"
    token_hash = hash_token(runner_token)

    runner = Runner(
        name=name,
        os=runner_os,
        status="online",
        labels=labels,
        busy=False,
        token_hash=token_hash,
        repo_id=reg.repo_id,
        last_heartbeat=datetime.now(timezone.utc),
    )
    db.add(runner)
    await db.delete(reg)
    await db.commit()
    await db.refresh(runner)

    return {
        "runner_id": runner.id,
        "token": runner_token,
        "name": runner.name,
    }


@router.post("/actions/runner/heartbeat")
async def runner_heartbeat(request: Request, db: DbSession):
    """Runner sends periodic heartbeats to stay online."""
    runner = await _get_runner_from_token(request, db)
    runner.last_heartbeat = datetime.now(timezone.utc)
    runner.status = "online"
    await db.commit()
    return {"status": "ok"}


@router.get("/repos/{owner}/{repo}/actions/runner/jobs")
async def poll_for_jobs(
    owner: str, repo: str,
    request: Request,
    db: DbSession,
    labels: str = Query("self-hosted,linux"),
    timeout: int = Query(30, ge=1, le=60),
):
    """Long-poll for available jobs matching runner labels."""
    runner = await _get_runner_from_token(request, db)
    repository = await get_repo_or_404(owner, repo, db)
    runner_labels = set(labels.split(","))

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        result = await db.execute(
            select(WorkflowJob)
            .join(WorkflowRun, WorkflowJob.run_id == WorkflowRun.id)
            .where(
                WorkflowRun.repo_id == repository.id,
                WorkflowJob.status == "queued",
            )
            .order_by(WorkflowJob.created_at)
            .limit(10)
        )
        jobs = result.scalars().all()

        for job in jobs:
            job_labels = set(job.labels or ["self-hosted"])
            if job_labels & runner_labels:
                job.status = "in_progress"
                job.runner_id = runner.id
                job.runner_name = runner.name
                job.started_at = datetime.now(timezone.utc)

                runner.busy = True
                runner.status = "busy"
                await db.commit()

                run_result = await db.execute(
                    select(WorkflowRun).where(WorkflowRun.id == job.run_id)
                )
                run = run_result.scalar_one_or_none()
                if run and run.status == "queued":
                    run.status = "in_progress"
                    await db.commit()

                return {
                    "job_id": job.id,
                    "run_id": job.run_id,
                    "name": job.name,
                    "steps": job.steps or [],
                    "labels": job.labels,
                    "workflow_name": job.workflow_name,
                    "env": {},
                }

        await asyncio.sleep(2)
        await db.expire_all()

    return Response(status_code=204)


@router.patch("/repos/{owner}/{repo}/actions/runner/jobs/{job_id}")
async def update_job_progress(
    owner: str, repo: str, job_id: int,
    body: dict, request: Request, db: DbSession,
):
    """Runner reports step progress."""
    runner = await _get_runner_from_token(request, db)
    result = await db.execute(
        select(WorkflowJob).where(WorkflowJob.id == job_id, WorkflowJob.runner_id == runner.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if "steps" in body:
        job.steps = body["steps"]

    await db.commit()
    return {"status": "updated"}


@router.post("/repos/{owner}/{repo}/actions/runner/jobs/{job_id}/complete")
async def complete_job(
    owner: str, repo: str, job_id: int,
    body: dict, request: Request, db: DbSession,
):
    """Runner reports job completion."""
    runner = await _get_runner_from_token(request, db)
    result = await db.execute(
        select(WorkflowJob).where(WorkflowJob.id == job_id, WorkflowJob.runner_id == runner.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    conclusion = body.get("conclusion", "success")
    job.status = "completed"
    job.conclusion = conclusion
    job.completed_at = datetime.now(timezone.utc)

    if "steps" in body:
        job.steps = body["steps"]

    runner.busy = False
    runner.status = "online"
    await db.commit()

    await dispatch_ready_jobs(db, job.run_id)
    await check_run_completion(db, job.run_id)
    await db.commit()

    return {"status": "completed", "conclusion": conclusion}


@router.post("/repos/{owner}/{repo}/actions/runner/jobs/{job_id}/logs")
async def upload_job_logs(
    owner: str, repo: str, job_id: int,
    request: Request, db: DbSession,
):
    """Accept log upload from runner."""
    runner = await _get_runner_from_token(request, db)
    result = await db.execute(
        select(WorkflowJob).where(WorkflowJob.id == job_id, WorkflowJob.runner_id == runner.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    log_data = await request.body()
    log_dir = os.path.join(settings.DATA_DIR, "logs", "jobs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{job_id}.log")
    with open(log_path, "ab") as f:
        f.write(log_data)

    return {"status": "ok"}
