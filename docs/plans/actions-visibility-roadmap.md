# Actions Visibility Roadmap

## Goal

Flesh out the GitHub Actions API and frontend surfaces enough that users can
see workflow runs, jobs, step state, runner state, and logs for repositories in
the emulator.

This roadmap intentionally separates visibility from full workflow execution.
The first usable milestone is: a pushed workflow creates a run, a runner can
claim or complete jobs, and the Web UI shows what happened. The preferred
execution target is the real `actions/runner` binary for maximum compatibility;
the bundled Python runner is a fallback for bootstrap, tests, and deterministic
simulation.

## Current State

- `docker-compose.yml` defines an `actions-runner` service that builds
  `runner/Dockerfile`.
- `runner/runner.py` can register with the emulator, heartbeat, poll for jobs,
  report progress, complete jobs, and upload logs.
- `runner/runner.py` currently simulates step execution; it does not run the
  workflow `run:` shell commands.
- `app/services/workflow_service.py` detects `.github/workflows/*.yml`, creates
  `Workflow`, `WorkflowRun`, and `WorkflowJob` rows, supports basic trigger
  matching, dependency ordering, and matrix expansion.
- `app/api/actions.py`, `app/api/actions_runners.py`, and
  `app/api/actions_dispatch.py` expose a repository-scoped API surface for
  workflows, runs, jobs, variables, secrets, runners, and custom runner
  dispatch.
- `app/api/actions_pipelines.py` and `app/api/actions_distributed_task.py`
  provide partial GHES/Azure Pipelines-style compatibility endpoints for the
  real `actions/runner` binary.
- The Web UI has an Actions tab, run list, run detail, job detail, runner list,
  and log view.
- Dedicated Actions API and Web UI tests exist in `tests/test_actions_api.py`
  and `tests/test_web_actions.py`.
- `make actions-runner-env` bootstraps `.env` values for the compose
  `actions-runner` service.
- `make actions-ui-smoke` runs desktop Playwright validation against a live UI
  when Playwright and a running stack are available.

## Target User Experience

Repository users should be able to open:

- `/ui/{owner}/{repo}/actions`
- `/ui/{owner}/{repo}/actions/runs/{run_id}`
- `/ui/{owner}/{repo}/actions/jobs/{job_id}`
- `/ui/{owner}/{repo}/actions/runners`

Those pages should show enough state to understand:

- which workflows exist
- which runs were requested
- run status and conclusion
- jobs in each run
- step status and conclusion
- runner assignment and runner health
- basic logs if available

## Work Items

- `docs/tasks/done/actions-visible-api-and-web-ui.md`
- `docs/tasks/pending/actions-runner-compose-bootstrap.md`
- `docs/tasks/pending/actions-job-execution-loop.md`
- `docs/tasks/pending/actions-hosted-runner-feasibility.md`

## Implementation Order

1. Build read-only web visibility on top of existing Actions database state.
   Complete.
2. Add API/read-model gaps needed by the UI, including a single-job endpoint and
   log download/read endpoint.
   Complete.
3. Add tests that create workflow/run/job rows and assert page/API rendering.
   Complete.
4. Make `docker-compose.yml` runner startup practical by documenting or
   automating token creation.
   Bootstrap helper and Make target complete; live compose execution could not
   be verified in this environment because no compose provider is installed.
5. Preserve the current simulated runner path until the UI is useful.
   Complete.
6. Prioritize a real `actions/runner` compatibility spike before expanding the
   Python runner into a larger execution engine.
   Pending.
7. Complete hosted-runner feasibility research before spending time trying to
   route emulator jobs to GitHub-owned runners.
   Proposed runner-strategy ADR complete; real-runner spike still pending.

## Non-Goals For First Visibility Milestone

- Full GitHub Actions expression evaluation.
- `uses:` action execution.
- Marketplace action download and execution.
- Artifact storage.
- Cache storage.
- Service containers and job containers.
- OIDC and `GITHUB_TOKEN` permission emulation.
- GitHub-hosted runner integration.
- Reimplementing the full runner runtime in Python.

## Evidence Required

- Dedicated tests for Actions API and UI routes.
  Complete: `tests/test_actions_api.py` and `tests/test_web_actions.py`.
- Docker Compose validation using the `github-emulator` and `actions-runner`
  services, or the real-runner service variant once it exists.
  Compose bootstrap and smoke targets exist. Live compose validation could not
  run in this environment because Docker has no compose provider installed.
- Playwright-driven desktop validation of the Actions UI against the running
  compose stack.
  Desktop Playwright MCP validation ran against a live local server. The
  compose-targeted script is `scripts/actions-ui-smoke-playwright.py`.
- A manual smoke path documented in `README.md` or a task note:
  create repo, add workflow, push, observe run/jobs in UI.
  README documents compose runner bootstrap and desktop smoke commands.
- Screenshot or route-level assertion coverage for the repo Actions tab.
  Complete: tests assert the Actions tab and Playwright captured a desktop
  screenshot of the runners page.
- Clear result from the hosted-runner feasibility task.
  Complete at ADR level: `docs/decisions/ADR-0001-actions-runner-strategy.md`
  prefers real `actions/runner` compatibility over GitHub-owned hosted runners.
