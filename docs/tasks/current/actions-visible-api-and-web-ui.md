# Task: Actions Visible API and Web UI

## Goal

Expose enough GitHub Actions state in the REST API and Web UI for users to
visualize workflows, runs, jobs, steps, runner assignment, and available logs.

## Context

The backend already creates workflow/run/job rows and has runner dispatch
endpoints, but the Web UI does not expose any of this. The current UI repo
navigation only includes Code, Issues, and Pull requests.

## Acceptance Criteria

- [ ] Repository navigation includes an Actions tab.
- [ ] `/ui/{owner}/{repo}/actions` lists workflows and recent workflow runs.
- [ ] `/ui/{owner}/{repo}/actions/runs/{run_id}` shows run metadata, jobs,
      status, conclusion, commit SHA, branch, actor, and event.
- [ ] `/ui/{owner}/{repo}/actions/jobs/{job_id}` shows job metadata, steps,
      runner name/id, timestamps, status, conclusion, and logs when present.
- [ ] `/ui/{owner}/{repo}/actions/runners` lists repository runners with name,
      labels, status, busy state, OS, and last heartbeat when available.
- [ ] API surface includes any missing read endpoints the UI needs, especially
      a single job endpoint and a job log endpoint.
- [ ] Empty states are useful for repos with no workflows, no runs, no jobs, or
      no registered runners.
- [ ] Existing private repository visibility rules are respected.
- [ ] Tests cover the Actions tab, run list, run detail, job detail, runner
      list, and log display/read endpoint.
- [ ] Playwright desktop validation covers the Actions tab, run list, run
      detail, job detail, runner list, empty states, and log display.
- [ ] Validation runs against a live server started from the Docker Compose
      stack, not only an in-process ASGI test client.

## Files Likely Involved

- `app/web/routes.py`
- `app/web/templates/_repo_nav.html`
- `app/web/templates/actions.html`
- `app/web/templates/action_run_detail.html`
- `app/web/templates/action_job_detail.html`
- `app/web/templates/action_runners.html`
- `app/web/static/css/web.css`
- `app/api/actions.py`
- `app/api/actions_runners.py`
- `tests/test_actions_api.py`
- `tests/test_web_actions.py`
- `tests/test_web_actions_playwright.py` or `scripts/actions-ui-smoke.*`

## Design Notes

- Prefer read-only views first; controls such as rerun/cancel can follow after
  state visualization is stable.
- Keep the UI dense and repository-oriented, matching the existing Primer-based
  web templates.
- Use status labels consistently:
  `queued`, `waiting`, `in_progress`, `completed`.
- Use conclusion labels consistently:
  `success`, `failure`, `cancelled`, `skipped`, `neutral`, `timed_out`.
- Make logs optional because current log upload writes files under
  `{DATA_DIR}/logs/jobs/{job_id}.log`.
- Playwright coverage is desktop-only unless a later task explicitly adds
  mobile requirements.

## Status

Current

## Notes

- The first implementation can visualize simulated jobs. It does not need to
  prove real shell execution.
- Add a task note if the current database model lacks fields needed by the UI
  instead of overloading unrelated columns.
- Use the compose stack as the end-to-end validation target so the runner,
  service URLs, cookies, static assets, and templates are checked together.
