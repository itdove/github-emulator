# Bug: PR web merge can close PR without advancing base ref

## Summary

Merging a pull request from the web UI could mark the PR as merged while leaving
the base branch unchanged.

## Reproduction

1. Open a git-backed pull request with real base and head branch refs.
2. Sign in through the web UI.
3. Click "Merge pull request".
4. Visit `/ui/<owner>/<repo>/commits/<base>`.

## Expected

The base branch advances to the merge commit and the commits page shows the new
merge commit at the top.

## Actual

The PR was marked closed/merged and `merge_commit_sha` was recorded, but
`refs/heads/<base>` still pointed at the previous base commit. On the observed
deployment, PR #3 recorded head SHA `374b60dcf434151361f51111fc49f3dceccf0c9a`
as the merge commit while `refs/heads/main` remained at
`1b6492023a80d5f9b523239a6492e345d56c6687`.

## Cause

The merge helper invoked `git merge --no-ff` without guaranteed author and
committer environment. On deployments without global git identity configured,
git failed to create the merge commit. The route swallowed the failure and kept
the DB-only merged state.

## Fix

Set deterministic Git author and committer environment for merge, squash,
rebase, checkout, and push operations performed by the merge helper. Added a
web merge regression that verifies the base branch ref advances to the recorded
merge commit.

## Verification

```bash
uv run pytest tests/test_pulls_api.py::test_pr_web_merge_button_merges_pull_request -v
```

Result: passed.
