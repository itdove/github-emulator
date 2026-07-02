# Task: Actions Job Execution Loop

## Goal

Prove and implement the minimum real execution path for workflow jobs, with the
real `actions/runner` binary as the preferred compatibility target.

## Context

The current custom Python runner registers, polls, reports progress, and marks
steps complete. It does not execute workflow `run:` commands because the server
only sends minimal step metadata to the runner.

The desired long-term outcome is maximum compatibility through the real
`actions/runner` binary. The Python runner should remain available as a
simulation and development fallback unless there is a deliberate decision to
expand it.

## Acceptance Criteria

- [ ] Build or document a Docker image/service variant that runs the real
      `actions/runner` binary against the emulator.
- [ ] Verify real runner registration against the emulator.
- [ ] Verify real runner session/message polling against the emulator.
- [ ] Send job payloads rich enough for the real runner to execute at least a
      simple shell step.
- [ ] Capture real runner timeline updates, logs, job completion, and failure
      results.
- [ ] Preserve enough workflow/job/step metadata in the database to support the
      real runner payloads and the Web UI.
- [ ] Keep the Python runner usable as a simulation fallback.
- [ ] Add tests or a repeatable smoke script for success, failure, skipped
      dependent jobs, and log capture.

## Files Likely Involved

- `app/services/workflow_service.py`
- `app/models/actions.py`
- `app/api/actions_dispatch.py`
- `app/api/actions_pipelines.py`
- `app/api/actions_distributed_task.py`
- `runner/runner.py`
- `runner/Dockerfile`
- `docker-compose.yml`
- `tests/test_actions_execution.py`

## Open Design Question

How much of the GHES/Azure Pipelines runner protocol must be implemented before
the real `actions/runner` can execute a simple local job?

## Status

Pending

## Notes

- This has security implications because workflow code is user-controlled.
- If enabled by default, the runner should be clearly scoped to local/testing
  environments only.
- Do not grow the Python runner into a full Actions runtime unless the real
  runner path is proven infeasible or too expensive for the project's needs.
