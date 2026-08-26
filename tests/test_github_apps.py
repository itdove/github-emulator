"""Tests for GitHub App emulation — admin, JWT auth, installation tokens, verification."""

import hashlib
import time

import pytest
import pytest_asyncio
from jose import jwt

from tests.conftest import API, auth_headers


@pytest_asyncio.fixture
async def github_app(client):
    """Create a GitHub App via admin endpoint."""
    resp = await client.post(
        "/admin/api/apps",
        json={"name": "test-app", "owner": "admin"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def installation(client, github_app):
    """Install the app on an org."""
    resp = await client.post(
        f"/admin/api/apps/{github_app['app_id']}/installations",
        json={"owner": "admin"},
    )
    assert resp.status_code == 201
    return resp.json()


def _make_jwt(app_id: int, private_key: str) -> str:
    now = int(time.time())
    payload = {"iss": str(app_id), "iat": now, "exp": now + 600}
    return jwt.encode(payload, private_key, algorithm="RS256")


def _jwt_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_app(client):
    resp = await client.post(
        "/admin/api/apps",
        json={"name": "my-app", "owner": "admin"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-app"
    assert data["app_id"] >= 1
    assert "private_key" in data
    assert data["private_key"].startswith("-----BEGIN RSA PRIVATE KEY-----")
    assert data["client_id"].startswith("Iv1.")


@pytest.mark.asyncio
async def test_list_apps(client, github_app):
    resp = await client.get("/admin/api/apps")
    assert resp.status_code == 200
    apps = resp.json()
    assert len(apps) >= 1
    assert any(a["app_id"] == github_app["app_id"] for a in apps)


@pytest.mark.asyncio
async def test_get_app_details(client, github_app):
    resp = await client.get(f"/admin/api/apps/{github_app['app_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-app"
    assert data["slug"] == "test-app"


@pytest.mark.asyncio
async def test_get_app_not_found(client):
    resp = await client.get("/admin/api/apps/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_private_key(client, github_app):
    resp = await client.get(f"/admin/api/apps/{github_app['app_id']}/private-key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["private_key"].startswith("-----BEGIN RSA PRIVATE KEY-----")


@pytest.mark.asyncio
async def test_regenerate_private_key(client, github_app):
    old_key = github_app["private_key"]
    resp = await client.post(
        f"/admin/api/apps/{github_app['app_id']}/private-key/regenerate"
    )
    assert resp.status_code == 200
    new_key = resp.json()["private_key"]
    assert new_key != old_key
    assert new_key.startswith("-----BEGIN RSA PRIVATE KEY-----")


@pytest.mark.asyncio
async def test_create_installation(client, github_app):
    resp = await client.post(
        f"/admin/api/apps/{github_app['app_id']}/installations",
        json={"owner": "test-org"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["owner"] == "test-org"
    assert data["app_id"] == github_app["app_id"]


@pytest.mark.asyncio
async def test_create_installation_with_repo(client, github_app):
    resp = await client.post(
        f"/admin/api/apps/{github_app['app_id']}/installations",
        json={"owner": "test-org", "repo": "my-repo"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["repo"] == "my-repo"


# ---------------------------------------------------------------------------
# JWT authentication — GitHub App API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_authenticated_app(client, github_app):
    token = _make_jwt(github_app["app_id"], github_app["private_key"])
    resp = await client.get(f"{API}/app", headers=_jwt_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == github_app["app_id"]
    assert data["slug"] == github_app["slug"]


@pytest.mark.asyncio
async def test_get_app_no_auth(client):
    resp = await client.get(f"{API}/app")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_app_bad_jwt(client):
    resp = await client.get(
        f"{API}/app", headers=_jwt_headers("not-a-jwt")
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_app_installations_jwt(client, github_app, installation):
    token = _make_jwt(github_app["app_id"], github_app["private_key"])
    resp = await client.get(
        f"{API}/app/installations", headers=_jwt_headers(token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == installation["id"]


# ---------------------------------------------------------------------------
# Installation access tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_installation_access_token(client, github_app, installation):
    jwt_token = _make_jwt(github_app["app_id"], github_app["private_key"])
    resp = await client.post(
        f"{API}/app/installations/{installation['id']}/access_tokens",
        headers=_jwt_headers(jwt_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"].startswith("ghs_")
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_installation_token_wrong_app(client, github_app, installation):
    """JWT for a different app can't create tokens for another app's installation."""
    # Create a second app
    resp = await client.post(
        "/admin/api/apps",
        json={"name": "other-app", "owner": "admin"},
    )
    other_app = resp.json()
    other_jwt = _make_jwt(other_app["app_id"], other_app["private_key"])

    resp = await client.post(
        f"{API}/app/installations/{installation['id']}/access_tokens",
        headers=_jwt_headers(other_jwt),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Installation token authenticates API calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_installation_token_auth(client, admin_user, github_app, installation):
    """Installation token can authenticate API calls as the app owner."""
    jwt_token = _make_jwt(github_app["app_id"], github_app["private_key"])
    resp = await client.post(
        f"{API}/app/installations/{installation['id']}/access_tokens",
        headers=_jwt_headers(jwt_token),
    )
    inst_token = resp.json()["token"]

    resp = await client.get(
        f"{API}/user",
        headers={"Authorization": f"token {inst_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["login"] == "admin"


# ---------------------------------------------------------------------------
# Permissive mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permissive_mode_accepts_any_jwt(client, github_app):
    """In permissive mode, any well-formed JWT with correct iss is accepted."""
    from app.config import settings
    original = settings.APP_JWT_PERMISSIVE
    settings.APP_JWT_PERMISSIVE = True
    try:
        # Create JWT with a completely different key
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        token = _make_jwt(github_app["app_id"], other_pem)
        resp = await client.get(f"{API}/app", headers=_jwt_headers(token))
        assert resp.status_code == 200
    finally:
        settings.APP_JWT_PERMISSIVE = original


@pytest.mark.asyncio
async def test_strict_mode_rejects_wrong_key(client, github_app):
    """In strict mode, JWT signed with wrong key is rejected."""
    from app.config import settings
    original = settings.APP_JWT_PERMISSIVE
    settings.APP_JWT_PERMISSIVE = False
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        token = _make_jwt(github_app["app_id"], other_pem)
        resp = await client.get(f"{API}/app", headers=_jwt_headers(token))
        assert resp.status_code == 401
    finally:
        settings.APP_JWT_PERMISSIVE = original


@pytest.mark.asyncio
async def test_strict_mode_accepts_correct_key(client, github_app):
    """In strict mode, JWT signed with correct key is accepted."""
    from app.config import settings
    original = settings.APP_JWT_PERMISSIVE
    settings.APP_JWT_PERMISSIVE = False
    try:
        token = _make_jwt(github_app["app_id"], github_app["private_key"])
        resp = await client.get(f"{API}/app", headers=_jwt_headers(token))
        assert resp.status_code == 200
    finally:
        settings.APP_JWT_PERMISSIVE = original


# ---------------------------------------------------------------------------
# Commit verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_commit_verified_with_installation_token(
    client, admin_user, github_app, installation, test_repo_with_init
):
    """Commits created via installation token should have verified: true."""
    owner, repo_name, _ = test_repo_with_init

    # Get installation token
    jwt_token = _make_jwt(github_app["app_id"], github_app["private_key"])
    resp = await client.post(
        f"{API}/app/installations/{installation['id']}/access_tokens",
        headers=_jwt_headers(jwt_token),
    )
    inst_token = resp.json()["token"]
    inst_headers = {"Authorization": f"token {inst_token}"}

    # List refs to find HEAD
    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/refs",
        headers=inst_headers,
    )
    if resp.status_code != 200 or not resp.json():
        pytest.skip("No refs available")

    head_sha = resp.json()[0]["object"]["sha"]
    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}",
        headers=inst_headers,
    )
    tree_sha = resp.json()["tree"]["sha"]

    # Create commit with installation token
    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/commits",
        json={"message": "verified commit", "tree": tree_sha, "parents": [head_sha]},
        headers=inst_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["verification"]["verified"] is True
    assert data["verification"]["reason"] == "valid"


@pytest.mark.asyncio
async def test_verified_commit_readable_with_pat(
    client, admin_user, admin_token, github_app, installation, test_repo_with_init
):
    """Verified commit should show verified: true even when read with a PAT."""
    owner, repo_name, _ = test_repo_with_init

    jwt_token = _make_jwt(github_app["app_id"], github_app["private_key"])
    resp = await client.post(
        f"{API}/app/installations/{installation['id']}/access_tokens",
        headers=_jwt_headers(jwt_token),
    )
    inst_token = resp.json()["token"]
    inst_headers = {"Authorization": f"token {inst_token}"}

    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/refs",
        headers=inst_headers,
    )
    if resp.status_code != 200 or not resp.json():
        pytest.skip("No refs available")

    head_sha = resp.json()[0]["object"]["sha"]
    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}",
        headers=inst_headers,
    )
    tree_sha = resp.json()["tree"]["sha"]

    # Create commit with installation token
    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/commits",
        json={"message": "verified commit", "tree": tree_sha, "parents": [head_sha]},
        headers=inst_headers,
    )
    assert resp.status_code == 201
    commit_sha = resp.json()["sha"]

    # Read same commit with PAT — should still be verified
    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/commits/{commit_sha}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["verification"]["verified"] is True
    assert resp.json()["verification"]["reason"] == "valid"


@pytest.mark.asyncio
async def test_commit_not_verified_with_pat(
    client, test_user, test_token, test_repo_with_init
):
    """Commits created via PAT should have verified: false."""
    owner, repo_name, _ = test_repo_with_init

    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/refs",
        headers=auth_headers(test_token),
    )
    if resp.status_code != 200 or not resp.json():
        pytest.skip("No refs available")

    head_sha = resp.json()[0]["object"]["sha"]
    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}",
        headers=auth_headers(test_token),
    )
    tree_sha = resp.json()["tree"]["sha"]

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/commits",
        json={"message": "unverified commit", "tree": tree_sha, "parents": [head_sha]},
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["verification"]["verified"] is False
