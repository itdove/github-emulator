"""Regression tests for SQLite writer-lock handling."""

import sqlite3
from contextlib import contextmanager

import pytest
from sqlalchemy import func, select

from app.models.import_job import ImportJob
from app.models.repository import Repository
from tests.conftest import auth_headers

API = "/api/v3"


@contextmanager
def held_sqlite_writer_lock(db_path):
    con = sqlite3.connect(db_path, timeout=0.1, isolation_level=None)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE users SET login = login WHERE id = 1")
        yield
    finally:
        con.rollback()
        con.close()


@pytest.mark.asyncio
async def test_admin_import_repo_returns_retryable_503_on_sqlite_lock(
    client, db_session, test_user, test_token, tmp_path
):
    """Import job creation should not expose SQLite lock as HTTP 500."""
    with held_sqlite_writer_lock(tmp_path / "test.db"):
        resp = await client.post(
            f"{API}/admin/repos/import",
            json={"url": "https://github.com/octocat/Hello-World", "owner": "testuser"},
            headers=auth_headers(test_token),
        )

    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "1"
    body = resp.json()
    assert body["message"] == "Database is busy, retry the request"
    assert body["errors"] == [{"resource": "Database", "code": "sqlite_locked"}]

    count = (
        await db_session.execute(select(func.count(ImportJob.id)))
    ).scalar_one()
    assert count == 0

    resp = await client.post(
        f"{API}/admin/repos/import",
        json={"url": "https://github.com/octocat/Hello-World", "owner": "testuser"},
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 202
    assert resp.json()["repo_name"] == "Hello-World"


@pytest.mark.asyncio
async def test_delete_repo_returns_retryable_503_on_sqlite_lock_without_partial_delete(
    client, db_session, test_user, test_token, tmp_path
):
    """Repository delete should rollback cleanly when SQLite remains locked."""
    resp = await client.post(
        f"{API}/user/repos",
        json={"name": "sqlite-lock-delete", "auto_init": True},
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 201

    with held_sqlite_writer_lock(tmp_path / "test.db"):
        resp = await client.delete(
            f"{API}/repos/testuser/sqlite-lock-delete",
            headers=auth_headers(test_token),
        )

    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "1"
    assert resp.json()["errors"] == [
        {"resource": "Database", "code": "sqlite_locked"}
    ]

    repo = (
        await db_session.execute(
            select(Repository).where(
                Repository.full_name == "testuser/sqlite-lock-delete"
            )
        )
    ).scalar_one_or_none()
    assert repo is not None

    resp = await client.delete(
        f"{API}/repos/testuser/sqlite-lock-delete",
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 204
