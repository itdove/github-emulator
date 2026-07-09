# Task: Seed a Default Admin Personal Access Token

## Goal

On startup (when `SEED_DATA=true` or equivalent), create a well-known admin PAT
so that API consumers can authenticate without manually creating a token first.

## Context

The emulator seeds an admin user (`admin`/`admin`) on startup, but no Personal
Access Token is created. API clients that use `Authorization: Bearer <token>` or
`Authorization: token <token>` have no way to authenticate out of the box.

This blocks downstream automation. For example, the `epic-code-gen` skill uses
`github_utils.py` which sends `Authorization: Bearer <token>` for all API calls
(fork creation, PR creation, push). Without a seeded PAT, these calls fail with
401 even though the admin user exists.

Basic auth extracts the password and looks it up as a PAT hash, so
`admin:admin` also fails for API calls unless a PAT with the raw value `admin`
exists.

## Proposed Behavior

- During database seeding, create a PAT for the admin user with a well-known
  raw token value (e.g. `ghp_admin_default_token` or simply `admin`).
- The token should have full scope (repos, orgs, admin).
- Document the default token in the README and CLAUDE.md.
- Optionally support a `DEFAULT_ADMIN_TOKEN` environment variable to override
  the seeded value.

## Acceptance Criteria

- [x] After a fresh startup with `SEED_DATA=true`, the admin user has a PAT.
- [x] `curl -H "Authorization: token <default-token>" http://localhost:8080/api/v3/user`
      returns the admin user.
- [x] `Authorization: Basic base64(admin:<default-token>)` also works.
- [x] The default token value is documented.
- [x] Existing tests are not broken.

## Motivation

The end-to-end demo pipeline (`var/demos/end-to-end/`) needs to call the GitHub
emulator API from skills like `epic-code-gen` to create forks and submit PRs.
Currently there is no way to obtain an API token without interactive UI access
or a separate admin API call, which breaks fully-automated workflows.

## Status

Done.

## Implementation

- Added `GITHUB_EMULATOR_DEFAULT_ADMIN_TOKEN`, defaulting to
  `ghp_admin_default_token`.
- Added `GITHUB_EMULATOR_SEED_DATA`, defaulting to `true`, as the explicit
  startup seed gate.
- Startup seeding now creates the admin user on a fresh database and ensures a
  `default-admin-token` PAT exists for that user with broad admin scopes.
- The seed operation is idempotent across restarts and updates the seeded token
  record if the configured raw token already exists.
- Documented the default token and override in `README.md` and `CLAUDE.md`.
- Added usage guide: `docs/guides/default-admin-pat.md`.

## Verification

- `uv run pytest tests/test_seed_admin_pat.py tests/test_auth.py -v`
  passed.
- `uv run pytest tests/ -v` passed: 249 tests.
