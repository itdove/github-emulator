#!/usr/bin/env python
"""Queue a minimal Actions workflow run for real-runner validation."""

from __future__ import annotations

import argparse
import asyncio
import os

DEFAULT_DATA_DIR = "/tmp/ghemu-actions-real-runner"
DEFAULT_DB_URL = (
    "sqlite+aiosqlite:////tmp/ghemu-actions-real-runner/github_emulator.db"
)

os.environ.setdefault("GITHUB_EMULATOR_DATA_DIR", DEFAULT_DATA_DIR)
os.environ.setdefault("GITHUB_EMULATOR_DATABASE_URL", DEFAULT_DB_URL)
os.environ.setdefault("GITHUB_EMULATOR_BASE_URL", "http://ghemu.local:8000")
os.environ.setdefault("GITHUB_EMULATOR_SSH_ENABLED", "false")

from sqlalchemy import select  # noqa: E402

from app.database import async_session, init_db  # noqa: E402
from app.models.actions import Workflow  # noqa: E402
from app.models.repository import Repository  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.workflow_service import create_workflow_run  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="admin/test-repo")
    parser.add_argument("--actor", default="admin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--path", default=".github/workflows/real-runner-smoke.yml")
    parser.add_argument("--sha", default="1" * 40)
    parser.add_argument("--script", default="echo real-runner-smoke")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    workflow_yaml = {
        "name": "Real runner smoke",
        "on": ["push"],
        "jobs": {
            "smoke": {
                "runs-on": "self-hosted",
                "steps": [
                    {
                        "name": "Say hello",
                        "run": args.script,
                    }
                ],
            }
        },
    }

    await init_db()
    async with async_session() as db:
        repo = (
            await db.execute(select(Repository).where(Repository.full_name == args.repo))
        ).scalar_one()
        actor = (
            await db.execute(select(User).where(User.login == args.actor))
        ).scalar_one()
        workflow = (
            await db.execute(
                select(Workflow).where(
                    Workflow.repo_id == repo.id,
                    Workflow.path == args.path,
                )
            )
        ).scalar_one_or_none()
        if workflow is None:
            workflow = Workflow(
                repo_id=repo.id,
                name="Real runner smoke",
                path=args.path,
            )
            db.add(workflow)
            await db.flush()

        run = await create_workflow_run(
            db,
            workflow,
            workflow_yaml,
            "push",
            {"ref": f"refs/heads/{args.branch}"},
            actor,
            args.sha,
            args.branch,
        )
        await db.commit()
        print(f"created run {run.id}")


if __name__ == "__main__":
    asyncio.run(main())
