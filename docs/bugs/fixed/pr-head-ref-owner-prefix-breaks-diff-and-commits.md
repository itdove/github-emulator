# Bug: PR head refs with owner prefix break commits and diffs

## Summary

Pull requests could store a GitHub label-style head ref such as
`opendatahub-io:epic/RHAI-2` in `PullRequest.head_ref`. Git operations in the
emulator expect a local branch ref such as `epic/RHAI-2`, so PR commits and
files changed views could not resolve the head commit.

## Status

Fixed.

## Reproduction

1. Open PR #3 in the deployed emulator:
   `http://github.local/ui/opendatahub-io/odh-cli/pulls/3`
2. Open the Files changed tab:
   `http://github.local/ui/opendatahub-io/odh-cli/pulls/3?tab=files`
3. Inspect the PR API:
   `GET /api/v3/repos/opendatahub-io/odh-cli/pulls/3`
4. Inspect repository branches:
   `GET /api/v3/repos/opendatahub-io/odh-cli/branches`

## Expected

- The PR stores or resolves a git-usable head ref.
- PR head SHA resolves to the actual branch tip.
- Commits tab lists commits in `base..head`.
- Files changed tab renders the diff for `base...head`.
- The displayed head label is formatted once, for example
  `opendatahub-io:epic/RHAI-2`.

## Actual

- PR #3 stored `head.ref` as `opendatahub-io:epic/RHAI-2`.
- PR #3 reported `head.sha` as
  `0000000000000000000000000000000000000000`.
- The repository had a real branch named `epic/RHAI-2` with SHA
  `374b60dcf434151361f51111fc49f3dceccf0c9a`.
- `GET /api/v3/repos/opendatahub-io/odh-cli/pulls/3/files` returned `[]`.
- The Files changed tab showed "No file changes in this pull request."
- The PR header displayed a doubled owner label:
  `opendatahub-io:opendatahub-io:epic/RHAI-2`.

## Resolution

- Added `app.git.bare_repo.normalize_branch_ref()` to resolve same-repository
  label-style refs such as `owner:branch` to git-usable branch refs.
- Updated PR creation to store the normalized branch ref when it exists.
- Added runtime normalization for existing malformed PR rows so deployed data
  can resolve without a database migration.
- Updated PR JSON serialization to use resolved refs/SHAs and avoid doubled
  owner labels.
- Updated PR files, commits, web Files changed, web Commits, REST merge, and
  web merge paths to use resolved refs for git operations.
- Replaced the PR commits endpoint stub with real `base..head` git log output,
  while preserving the legacy placeholder response when no git-backed commits
  can be resolved.
- Added a regression test that mutates a PR row to `testuser:feature` plus a
  zero head SHA and verifies API JSON, commits, files, and web label rendering
  all recover through normalization.

## Verification

Ran:

```bash
uv run pytest tests/test_pulls_api.py -v
git diff --check
```

Result: 20 passed, 1 warning; diff whitespace check clean.
