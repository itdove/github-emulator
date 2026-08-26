"""Tests for Git Data API -- Trees."""

import pytest

from tests.conftest import API, auth_headers


@pytest.mark.asyncio
async def test_create_tree_with_sha(client, test_user, test_token, test_repo_with_init):
    """Create tree with explicit blob SHA."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    # Create a blob
    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/blobs",
        json={"content": "hello", "encoding": "utf-8"},
        headers=h,
    )
    assert resp.status_code == 201
    blob_sha = resp.json()["sha"]

    # Get base tree
    refs = await client.get(f"{API}/repos/{owner}/{repo_name}/git/refs", headers=h)
    head_sha = refs.json()[0]["object"]["sha"]
    commit = await client.get(f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}", headers=h)
    tree_sha = commit.json()["tree"]["sha"]

    # Create tree
    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/trees",
        json={
            "base_tree": tree_sha,
            "tree": [{"path": "file.py", "mode": "100644", "type": "blob", "sha": blob_sha}],
        },
        headers=h,
    )
    assert resp.status_code == 201
    assert "sha" in resp.json()


@pytest.mark.asyncio
async def test_create_tree_with_content(client, test_user, test_token, test_repo_with_init):
    """Create tree with inline content (auto-creates blob)."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/trees",
        json={
            "tree": [{"path": "new.txt", "mode": "100644", "type": "blob", "content": "hello world"}],
        },
        headers=h,
    )
    assert resp.status_code == 201
    assert "sha" in resp.json()


@pytest.mark.asyncio
async def test_create_tree_with_base64_content(client, test_user, test_token, test_repo_with_init):
    """Create tree with base64-encoded content."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    import base64
    encoded = base64.b64encode(b"binary data").decode()

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/trees",
        json={
            "tree": [{"path": "data.bin", "mode": "100644", "type": "blob", "content": encoded, "encoding": "base64"}],
        },
        headers=h,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_tree_with_base_tree_and_content(
    client, test_user, test_token, test_repo_with_init
):
    """Create tree with base_tree and inline content."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    refs = await client.get(f"{API}/repos/{owner}/{repo_name}/git/refs", headers=h)
    head_sha = refs.json()[0]["object"]["sha"]
    commit = await client.get(f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}", headers=h)
    tree_sha = commit.json()["tree"]["sha"]

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/trees",
        json={
            "base_tree": tree_sha,
            "tree": [{"path": "added.py", "mode": "100644", "type": "blob", "content": "print('hi')"}],
        },
        headers=h,
    )
    assert resp.status_code == 201

    # Verify new tree contains both old and new files
    new_tree_sha = resp.json()["sha"]
    tree_resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/trees/{new_tree_sha}",
        headers=h,
    )
    assert tree_resp.status_code == 200
    paths = [e["path"] for e in tree_resp.json()["tree"]]
    assert "added.py" in paths
    assert "README.md" in paths


@pytest.mark.asyncio
async def test_create_tree_nested_path(client, test_user, test_token, test_repo_with_init):
    """Create tree with nested path (e.g. backend/src/file.py)."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    refs = await client.get(f"{API}/repos/{owner}/{repo_name}/git/refs", headers=h)
    head_sha = refs.json()[0]["object"]["sha"]
    commit = await client.get(f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}", headers=h)
    tree_sha = commit.json()["tree"]["sha"]

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/blobs",
        json={"content": "print('nested')", "encoding": "utf-8"},
        headers=h,
    )
    assert resp.status_code == 201
    blob_sha = resp.json()["sha"]

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/trees",
        json={
            "base_tree": tree_sha,
            "tree": [{"path": "backend/src/app/main.py", "mode": "100644", "type": "blob", "sha": blob_sha}],
        },
        headers=h,
    )
    assert resp.status_code == 201
    new_tree_sha = resp.json()["sha"]

    tree_resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/trees/{new_tree_sha}?recursive=1",
        headers=h,
    )
    assert tree_resp.status_code == 200
    paths = [e["path"] for e in tree_resp.json()["tree"]]
    assert "backend/src/app/main.py" in paths
    assert "README.md" in paths


@pytest.mark.asyncio
async def test_create_tree_empty_returns_422(client, test_user, test_token, test_repo_with_init):
    """Empty tree entries returns 422."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/trees",
        json={"tree": []},
        headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_tree(client, test_user, test_token, test_repo_with_init):
    """GET /git/trees/{sha} returns tree entries."""
    owner, repo_name, _ = test_repo_with_init
    h = auth_headers(test_token)

    refs = await client.get(f"{API}/repos/{owner}/{repo_name}/git/refs", headers=h)
    head_sha = refs.json()[0]["object"]["sha"]
    commit = await client.get(f"{API}/repos/{owner}/{repo_name}/git/commits/{head_sha}", headers=h)
    tree_sha = commit.json()["tree"]["sha"]

    resp = await client.get(f"{API}/repos/{owner}/{repo_name}/git/trees/{tree_sha}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sha"] == tree_sha
    assert len(data["tree"]) > 0
    assert "path" in data["tree"][0]
