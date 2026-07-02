# ADR-0001: Prefer Real Runner Compatibility for Actions

## Status

Proposed

## Context

The emulator has a partial GitHub Actions implementation:

- workflow discovery and run/job creation
- REST endpoints for workflows, runs, jobs, secrets, variables, and runners
- a custom Docker Compose runner service using `runner/runner.py`
- partial GHES/Azure Pipelines-style endpoints for possible real
  `actions/runner` compatibility

The project needs enough Actions API and frontend surface to visualize jobs.
It also needs a runner strategy. A natural question is whether GitHub-owned
hosted runners can be used by this emulator instead of running local or
self-hosted runners.

Official GitHub documentation describes GitHub-hosted runners as machines
provided by GitHub for GitHub Actions workflows. It describes self-hosted
runners as systems users deploy and manage to execute GitHub Actions jobs.

The emulator is not GitHub's Actions control plane. It owns its own scheduler,
database, API, repository storage, identity, runner tokens, and job lifecycle.

## Decision

Do not plan on using GitHub-owned hosted runners as the execution backend for
this emulator.

Use emulator-managed runners instead, with the real `actions/runner` binary as
the preferred compatibility target:

1. Make the real `actions/runner` binary work against the emulator's GHES/Azure
   Pipelines-style endpoints.
2. Keep the Docker Compose `actions-runner` service as the first local runner
   path, but evolve it toward the real runner if the compatibility spike proves
   viable.
3. Keep the custom Python runner as a bootstrap, test, and deterministic
   simulation fallback rather than the primary fidelity target.
4. If scaling is needed later, explore ephemeral self-hosted runners or
   Kubernetes-managed runner pools controlled by this emulator.

## Consequences

- The first Actions milestone can focus on API/UI visibility without depending
  on external GitHub billing, identity, or runner provisioning.
- Maximum workflow/runtime compatibility should come from the real runner
  protocol, not from reimplementing runner behavior in Python.
- The project still controls the emulator-side scheduler, API, storage, and
  runner token model.
- The emulator will not perfectly match GitHub-hosted runner images, lifecycle,
  billing, isolation, or tool preinstalls.
- The custom Python runner should remain useful for tests and development even
  if it never becomes a full Actions runtime.

## Evidence

- GitHub-hosted runners are GitHub-provided machines for GitHub Actions
  workflows:
  `https://docs.github.com/en/actions/concepts/runners/github-hosted-runners`
- Self-hosted runners are deployed and managed by the user:
  `https://docs.github.com/en/actions/concepts/runners/self-hosted-runners`
- Current repo evidence:
  - `docker-compose.yml` already defines an `actions-runner` service.
  - `runner/runner.py` already implements a custom runner loop.
  - `app/api/actions_pipelines.py` and
    `app/api/actions_distributed_task.py` already begin a real-runner
    compatibility path.

## Remaining Validation

- Confirm from official GHES Actions documentation whether GitHub-hosted
  runners are supported for self-managed GHES, and whether that support is
  relevant to a non-GitHub emulator.
- Run a spike with the real `actions/runner` binary against the emulator's
  compatibility endpoints.
- Identify the minimum additional GHES/Azure Pipelines endpoints and payload
  fields needed by the real runner for registration, job acquisition, timeline
  updates, log upload, and completion.
- Decide whether the custom Python runner should execute shell commands or stay
  a deterministic simulation runner for tests after the real-runner spike.
