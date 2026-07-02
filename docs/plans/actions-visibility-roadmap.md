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
- The Web UI has no Actions tab, run list, run detail, job detail, runner list,
  or log view.
- There are no dedicated Actions tests in `tests/`.

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

- `docs/tasks/current/actions-visible-api-and-web-ui.md`
- `docs/tasks/pending/actions-runner-compose-bootstrap.md`
- `docs/tasks/pending/actions-job-execution-loop.md`
- `docs/tasks/pending/actions-hosted-runner-feasibility.md`

## Implementation Order

1. Build read-only web visibility on top of existing Actions database state.
2. Add API/read-model gaps needed by the UI, including a single-job endpoint and
   log download/read endpoint.
3. Add tests that create workflow/run/job rows and assert page/API rendering.
4. Make `docker-compose.yml` runner startup practical by documenting or
   automating token creation.
5. Preserve the current simulated runner path until the UI is useful.
6. Prioritize a real `actions/runner` compatibility spike before expanding the
   Python runner into a larger execution engine.
7. Complete hosted-runner feasibility research before spending time trying to
   route emulator jobs to GitHub-owned runners.

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
- Docker Compose validation using the `github-emulator` and `actions-runner`
  services, or the real-runner service variant once it exists.
- Playwright-driven desktop validation of the Actions UI against the running
  compose stack.
- A manual smoke path documented in `README.md` or a task note:
  create repo, add workflow, push, observe run/jobs in UI.
- Screenshot or route-level assertion coverage for the repo Actions tab.
- Clear result from the hosted-runner feasibility task.
