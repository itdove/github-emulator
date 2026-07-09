"""Tests for startup admin user and PAT seeding."""

import base64

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.token import PersonalAccessToken
from app.models.user import User

API = "/api/v3"


@pytest.mark.asyncio
async def test_lifespan_seeds_admin_pat_when_seed_data_enabled(monkeypatch, tmp_path):
    from app import main as app_main

    calls = []

    async def fake_init_db():
        calls.append("init_db")

    async def fake_ensure_admin_user():
        calls.append("ensure_admin_user")

    monkeypatch.setattr(app_main, "init_db", fake_init_db)
    monkeypatch.setattr(app_main, "_ensure_admin_user", fake_ensure_admin_user)
    monkeypatch.setattr(app_main.settings, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(app_main.settings, "SEED_DATA", True)
    monkeypatch.setattr(app_main.settings, "SSH_ENABLED", False)

    async with app_main.lifespan(None):
        pass

    assert calls == ["init_db", "ensure_admin_user"]


@pytest.mark.asyncio
async def test_startup_seeds_default_admin_pat(
    client, db_engine, monkeypatch,
):
    from app import main as app_main

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(app_main, "async_session", session_factory)
    monkeypatch.setattr(app_main.settings, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(app_main.settings, "ADMIN_PASSWORD", "admin")
    monkeypatch.setattr(
        app_main.settings,
        "DEFAULT_ADMIN_TOKEN",
        "ghp_test_default_admin_token",
    )

    await app_main._ensure_admin_user()
    await app_main._ensure_admin_user()

    async with session_factory() as db:
        admin = (
            await db.execute(select(User).where(User.login == "admin"))
        ).scalar_one()
        token_count = (
            await db.execute(select(func.count(PersonalAccessToken.id)))
        ).scalar_one()
        pat = (
            await db.execute(
                select(PersonalAccessToken).where(
                    PersonalAccessToken.user_id == admin.id,
                    PersonalAccessToken.name == "default-admin-token",
                )
            )
        ).scalar_one()

    assert admin.site_admin is True
    assert token_count == 1
    assert pat.token_prefix == "ghp_test"
    assert {"repo", "user", "admin", "org", "admin:org"}.issubset(set(pat.scopes))

    resp = await client.get(
        f"{API}/user",
        headers={"Authorization": "token ghp_test_default_admin_token"},
    )
    assert resp.status_code == 200
    assert resp.json()["login"] == "admin"

    resp = await client.get(
        f"{API}/user",
        headers={"Authorization": "Bearer ghp_test_default_admin_token"},
    )
    assert resp.status_code == 200
    assert resp.json()["login"] == "admin"

    creds = base64.b64encode(b"admin:ghp_test_default_admin_token").decode()
    resp = await client.get(
        f"{API}/user",
        headers={"Authorization": f"Basic {creds}"},
    )
    assert resp.status_code == 200
    assert resp.json()["login"] == "admin"
