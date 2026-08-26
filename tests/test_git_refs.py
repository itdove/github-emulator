"""Tests for Git Data API -- References (refs)."""

import pytest

from tests.conftest import API, auth_headers


@pytest.mark.asyncio
async def test_get_ref_singular(client, test_user, test_token, test_repo_with_init):
    """GET /git/ref/heads/{branch} returns the ref object."""
    owner, repo_name, _ = test_repo_with_init

    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/ref/heads/main",
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ref"] == "refs/heads/main"
    assert "sha" in data["object"]
    assert data["object"]["type"] == "commit"


@pytest.mark.asyncio
async def test_get_ref_plural(client, test_user, test_token, test_repo_with_init):
    """GET /git/refs/heads/{branch} returns the same ref object (plural URL)."""
    owner, repo_name, _ = test_repo_with_init

    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/refs/heads/main",
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ref"] == "refs/heads/main"
    assert "sha" in data["object"]
    assert data["object"]["type"] == "commit"


@pytest.mark.asyncio
async def test_get_ref_singular_and_plural_match(
    client, test_user, test_token, test_repo_with_init
):
    """Both singular and plural URLs return the same SHA."""
    owner, repo_name, _ = test_repo_with_init

    resp1 = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/ref/heads/main",
        headers=auth_headers(test_token),
    )
    resp2 = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/refs/heads/main",
        headers=auth_headers(test_token),
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["object"]["sha"] == resp2.json()["object"]["sha"]


@pytest.mark.asyncio
async def test_get_ref_not_found(client, test_user, test_token, test_repo_with_init):
    """GET /git/ref/heads/nonexistent returns 404."""
    owner, repo_name, _ = test_repo_with_init

    resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/ref/heads/nonexistent",
        headers=auth_headers(test_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_ref(client, test_user, test_token, test_repo_with_init):
    """DELETE /git/refs/heads/{branch} removes the ref."""
    owner, repo_name, _ = test_repo_with_init

    # Create a new branch first
    refs_resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/refs",
        headers=auth_headers(test_token),
    )
    assert refs_resp.status_code == 200
    main_sha = refs_resp.json()[0]["object"]["sha"]

    create_resp = await client.post(
        f"{API}/repos/{owner}/{repo_name}/git/refs",
        json={"ref": "refs/heads/test-delete", "sha": main_sha},
        headers=auth_headers(test_token),
    )
    assert create_resp.status_code == 201

    # Delete it
    del_resp = await client.delete(
        f"{API}/repos/{owner}/{repo_name}/git/refs/heads/test-delete",
        headers=auth_headers(test_token),
    )
    assert del_resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"{API}/repos/{owner}/{repo_name}/git/ref/heads/test-delete",
        headers=auth_headers(test_token),
    )
    assert get_resp.status_code == 404
