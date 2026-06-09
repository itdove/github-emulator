"""GHES-internal distributed task endpoints for real actions/runner binary.

The real runner uses /_apis/distributedtask/ paths for session management
and job dispatch via long-poll. These endpoints implement the Azure Pipelines
agent protocol that the runner binary expects.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DbSession
from app.config import settings
from app.models.actions import Runner, RunnerSession, WorkflowJob, WorkflowRun
from app.services.auth_service import hash_token
from app.services.workflow_service import check_run_completion, dispatch_ready_jobs

router = APIRouter(tags=["actions-distributed-task"])


async def _get_runner_from_token(request: Request, db) -> Runner:
    """Authenticate a runner from Authorization header."""
    auth = request.headers.get("Authorization", "")
    token = ""
    if auth.startswith("Bearer "):
        token = auth[7:]
    elif auth.startswith("token "):
        token = auth[6:]
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    token_hash = hash_token(token)
    result = await db.execute(
        select(Runner).where(Runner.token_hash == token_hash)
    )
    runner = result.scalar_one_or_none()
    if runner is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return runner


@router.post("/_apis/distributedtask/connect")
async def dt_connect(request: Request, db: DbSession):
    """Session negotiation. Runner opens a long-lived session."""
    runner = await _get_runner_from_token(request, db)

    session_id = str(uuid.uuid4())
    session = RunnerSession(
        runner_id=runner.id,
        session_id=session_id,
        last_seen=datetime.now(timezone.utc),
    )
    db.add(session)

    runner.status = "online"
    runner.last_heartbeat = datetime.now(timezone.utc)
    await db.commit()

    base = settings.BASE_URL
    return {
        "sessionId": session_id,
        "ownerName": "github-emulator",
        "serviceUrls": {
            "messageQueueUrl": f"{base}/_apis/distributedtask",
            "jobDispatchUrl": f"{base}/_apis/distributedtask",
            "blobStoreUrl": f"{base}/_apis/distributedtask/blobs",
        },
    }


@router.get("/_apis/distributedtask/session/{session_id}/messages")
async def dt_get_messages(
    session_id: str, request: Request, db: DbSession,
):
    """Long-poll for job messages. Returns a PipelineAgentJobRequest when available."""
    runner = await _get_runner_from_token(request, db)

    result = await db.execute(
        select(RunnerSession).where(RunnerSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.last_seen = datetime.now(timezone.utc)
    await db.commit()

    deadline = asyncio.get_event_loop().time() + 30
    while asyncio.get_event_loop().time() < deadline:
        job_result = await db.execute(
            select(WorkflowJob)
            .where(
                WorkflowJob.status == "queued",
                WorkflowJob.runner_id.is_(None),
            )
            .order_by(WorkflowJob.created_at)
            .limit(1)
        )
        job = job_result.scalar_one_or_none()

        if job:
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
                "messageType": "PipelineAgentJobRequest",
                "body": {
                    "jobId": str(job.id),
                    "jobName": job.name,
                    "requestId": job.id,
                    "plan": {
                        "planId": str(job.run_id),
                    },
                    "timeline": {
                        "id": str(uuid.uuid4()),
                    },
                    "steps": [
                        {
                            "id": str(uuid.uuid4()),
                            "type": "task",
                            "name": s.get("name", f"Step {s.get('number', 0)}"),
                            "order": s.get("number", 0),
                        }
                        for s in (job.steps or [])
                    ],
                    "variables": {},
                    "resources": {
                        "repositories": [{
                            "alias": "self",
                            "id": str(run.repo_id) if run else "0",
                        }],
                    },
                },
            }

        await asyncio.sleep(2)
        await db.expire_all()

    return Response(status_code=204)


@router.delete("/_apis/distributedtask/session/{session_id}")
async def dt_delete_session(
    session_id: str, request: Request, db: DbSession,
):
    """Close a runner session."""
    result = await db.execute(
        select(RunnerSession).where(RunnerSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    runner_result = await db.execute(
        select(Runner).where(Runner.id == session.runner_id)
    )
    runner = runner_result.scalar_one_or_none()
    if runner:
        runner.status = "offline"
        runner.busy = False

    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}


@router.post("/_apis/distributedtask/jobs/{job_id}/timeline")
async def dt_update_timeline(
    job_id: int, request: Request, db: DbSession,
):
    """Runner reports step timeline updates."""
    runner = await _get_runner_from_token(request, db)
    body = await request.json()

    result = await db.execute(
        select(WorkflowJob).where(WorkflowJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    records = body.get("value", body.get("records", []))
    if records and job.steps:
        steps = list(job.steps)
        for record in records:
            order = record.get("order", 0)
            for step in steps:
                if step.get("number") == order:
                    if "state" in record:
                        state_map = {"Completed": "completed", "InProgress": "in_progress"}
                        step["status"] = state_map.get(record["state"], record["state"])
                    if "result" in record:
                        result_map = {"Succeeded": "success", "Failed": "failure", "Skipped": "skipped"}
                        step["conclusion"] = result_map.get(record["result"], record["result"])
                    break
        job.steps = steps

    await db.commit()
    return {"status": "ok"}


@router.post("/_apis/distributedtask/jobs/{job_id}/complete")
async def dt_complete_job(
    job_id: int, request: Request, db: DbSession,
):
    """Runner reports job completion."""
    runner = await _get_runner_from_token(request, db)
    body = await request.json()

    result = await db.execute(
        select(WorkflowJob).where(WorkflowJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result_str = body.get("result", "Succeeded")
    conclusion_map = {"Succeeded": "success", "Failed": "failure", "Cancelled": "cancelled"}
    job.status = "completed"
    job.conclusion = conclusion_map.get(result_str, "failure")
    job.completed_at = datetime.now(timezone.utc)

    runner.busy = False
    runner.status = "online"
    await db.commit()

    await dispatch_ready_jobs(db, job.run_id)
    await check_run_completion(db, job.run_id)
    await db.commit()

    return {"status": "completed"}
