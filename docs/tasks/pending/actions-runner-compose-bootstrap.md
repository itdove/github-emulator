# Task: Actions Runner Compose Bootstrap

## Goal

Make the `actions-runner` service in `docker-compose.yml` usable without manual
guesswork.

## Context

`docker-compose.yml` already contains an `actions-runner` service. It uses the
custom Python runner in `runner/runner.py` and expects:

- `GITHUB_EMULATOR_URL=https://github-emulator`
- `GITHUB_EMULATOR_TOKEN=${GITHUB_EMULATOR_RUNNER_TOKEN:-}`
- `RUNNER_REPO=${RUNNER_REPO:-admin/test-repo}`

The runner cannot register unless a valid admin PAT is supplied through
`GITHUB_EMULATOR_RUNNER_TOKEN`, and the default repo may not exist.

## Acceptance Criteria

- [ ] Document the exact bootstrap sequence for `docker compose up` with the
      runner enabled.
- [ ] Provide a Makefile target or script that creates the runner token and
      writes an `.env` value or prints export commands.
- [ ] Document how to choose `RUNNER_REPO`.
- [ ] Runner service fails clearly when token or repo is missing.
- [ ] Smoke test path proves runner registration, heartbeat, job polling, job
      completion, and UI visibility.
- [ ] Smoke test starts from Docker Compose and records the exact command
      sequence.
- [ ] Playwright desktop validation can run against the compose-served UI after
      the runner creates or completes at least one job.

## Files Likely Involved

- `docker-compose.yml`
- `Makefile`
- `runner/runner.py`
- `README.md`
- `scripts/`
- Playwright smoke script or pytest integration once the project chooses the
  test harness.

## Status

Pending

## Notes

- This task should happen after the UI can show runner state, otherwise the
  bootstrap success signal is only log output.
