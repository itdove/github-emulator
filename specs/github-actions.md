# GitHub Actions & Runners -- Comprehensive Specification Reference

This document compiles exhaustive technical details on GitHub Actions: workflow syntax, REST API endpoints, runner protocol internals, open-source implementations, and advanced features. Intended as a reference for building GitHub Actions emulation into the github-emulator project.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Workflow File Syntax](#2-workflow-file-syntax)
3. [Trigger Events](#3-trigger-events)
4. [Expression Syntax](#4-expression-syntax)
5. [Contexts](#5-contexts)
6. [Matrix Strategies](#6-matrix-strategies)
7. [Conditionals](#7-conditionals)
8. [REST API Endpoints](#8-rest-api-endpoints)
9. [Runner Protocol & Architecture](#9-runner-protocol--architecture)
10. [Runner Registration & Authentication](#10-runner-registration--authentication)
11. [Job Dispatch & Execution Lifecycle](#11-job-dispatch--execution-lifecycle)
12. [Environments](#12-environments)
13. [Secrets](#13-secrets)
14. [Variables](#14-variables)
15. [Artifacts](#15-artifacts)
16. [Caching](#16-caching)
17. [Concurrency](#17-concurrency)
18. [GITHUB_TOKEN & Permissions](#18-github_token--permissions)
19. [Service Containers](#19-service-containers)
20. [Job Containers](#20-job-containers)
21. [Workflow Commands](#21-workflow-commands)
22. [Problem Matchers](#22-problem-matchers)
23. [Custom Actions](#23-custom-actions)
24. [Reusable Workflows](#24-reusable-workflows)
25. [OIDC](#25-oidc)
26. [Security Considerations](#26-security-considerations)
27. [Usage Limits](#27-usage-limits)
28. [Default Environment Variables](#28-default-environment-variables)
29. [Open Source Implementations](#29-open-source-implementations)
30. [Implementation Guidance for Emulators](#30-implementation-guidance-for-emulators)
31. [Sources](#31-sources)

---

## 1. Architecture Overview

### 1.1 High-Level System Design

```
                    GitHub.com
    +------------------------------------------+
    |                                          |
    |  Webhook Event (push, PR, etc.)          |
    |         |                                |
    |         v                                |
    |  +---------------+                       |
    |  | Actions        |  Parses .github/     |
    |  | Service        |  workflows/*.yml     |
    |  | (Orchestrator) |                      |
    |  +-------+-------+                       |
    |          |                               |
    |          v                               |
    |  +---------------+                       |
    |  | Job Scheduler  |  Creates workflow    |
    |  | / Dispatcher   |  run, enqueues jobs  |
    |  +-------+-------+                       |
    |          |                               |
    |          v                               |
    |  +---------------+     Long-poll /       |
    |  | Message Broker |     Broker session   |
    |  | (Job Queue)    |<------------------+  |
    |  +-------+-------+                    |  |
    |          |                            |  |
    +----------+----------------------------+--+
               |                            |
               v                            |
    +------------------+         +------------------+
    | Runner (Agent)   |         | Runner (Agent)   |
    | - Listener       |         | - Listener       |
    | - Worker         |         | - Worker         |
    +------------------+         +------------------+
```

### 1.2 Azure Pipelines Heritage

GitHub Actions is built on Azure Pipelines infrastructure (Microsoft acquired GitHub in 2018):

- The runner agent (`actions/runner`) is a direct evolution of the Azure Pipelines agent (`microsoft/azure-pipelines-agent`), both written in C#/.NET
- The YAML workflow syntax borrows concepts from Azure Pipelines (stages, jobs, steps, matrices)
- The expression language (`${{ }}`) is derived from Azure Pipelines expressions
- The internal communication protocol uses `/_apis/distributedtask/` endpoints from Azure DevOps
- The primary backend is `https://pipelines.actions.githubusercontent.com`

### 1.3 Webhook-to-Workflow Triggering Flow

1. **Event Ingestion**: Git push, PR, issue comment, or other event emits an internal webhook event
2. **Workflow Discovery**: Actions service reads all `.github/workflows/*.yml` files at the relevant commit SHA
3. **Event Filtering**: Evaluates `on:` triggers, `branches`, `paths`, `types` filters
4. **Workflow Run Creation**: Creates a `workflow_run` record; parses each `job` as a schedulable unit
5. **Job Dependency Resolution**: Builds a DAG from `needs:` dependencies; independent jobs run in parallel
6. **Job Queuing**: Ready jobs placed in message queue with: repo ref, commit SHA, job definition, runner labels, encrypted secrets, session token

---

## 2. Workflow File Syntax

Workflow files live at `.github/workflows/<name>.yml` (or `.yaml`).

### 2.1 Top-Level Keys

| Key | Required | Description |
|-----|----------|-------------|
| `name` | No | Display name in the Actions tab |
| `run-name` | No | Dynamic name for workflow runs (supports expressions) |
| `on` | **Yes** | Events that trigger the workflow |
| `permissions` | No | Default GITHUB_TOKEN permissions for all jobs |
| `env` | No | Environment variables for all jobs/steps |
| `defaults` | No | Default settings (currently only `defaults.run`) |
| `concurrency` | No | Concurrency group configuration |
| `jobs` | **Yes** | Map of job IDs to job definitions |

```yaml
name: CI Pipeline
run-name: Deploy by @${{ github.actor }}

on:
  push:
    branches: [main]

permissions:
  contents: read

env:
  NODE_ENV: production

defaults:
  run:
    shell: bash
    working-directory: ./src

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm test
```

### 2.2 Job Keys

| Key | Required | Description |
|-----|----------|-------------|
| `runs-on` | Yes* | Runner label(s). *Not needed if using `uses` for reusable workflows |
| `name` | No | Display name (supports expressions) |
| `needs` | No | Job dependencies (string or array) |
| `if` | No | Conditional expression |
| `permissions` | No | Override workflow-level GITHUB_TOKEN permissions |
| `environment` | No | Deployment environment (name + optional URL) |
| `outputs` | No | Map of outputs for dependent jobs |
| `env` | No | Environment variables for all steps |
| `defaults` | No | Default run settings |
| `timeout-minutes` | No | Max runtime (default: 360) |
| `strategy` | No | Matrix strategy configuration |
| `continue-on-error` | No | Allow workflow to pass if job fails |
| `container` | No | Docker container for all steps |
| `services` | No | Sidecar service containers |
| `concurrency` | No | Job-level concurrency group |
| `uses` | No | Call a reusable workflow (instead of runs-on + steps) |
| `with` | No | Inputs for reusable workflow |
| `secrets` | No | Secrets for reusable workflow (or `inherit`) |
| `steps` | No | Ordered list of steps |

#### `runs-on` Values

```yaml
# Single label
runs-on: ubuntu-latest

# Multiple labels (AND logic -- runner must match ALL)
runs-on: [self-hosted, linux, x64]

# Expression
runs-on: ${{ matrix.os }}

# Group + labels
runs-on:
  group: my-runner-group
  labels: [linux, x64]
```

Standard GitHub-hosted runners: `ubuntu-latest`, `ubuntu-22.04`, `ubuntu-24.04`, `ubuntu-20.04`, `windows-latest`, `windows-2022`, `windows-2019`, `macos-latest`, `macos-14`, `macos-13`, `macos-12`.

### 2.3 Step Keys

| Key | Description |
|-----|-------------|
| `id` | Unique identifier for referencing outputs/outcome |
| `name` | Display name (supports expressions) |
| `if` | Conditional expression |
| `uses` | Action to run (mutually exclusive with `run`) |
| `run` | Shell command (mutually exclusive with `uses`) |
| `with` | Input parameters for action |
| `env` | Step-specific environment variables |
| `continue-on-error` | Allow job to continue if step fails |
| `timeout-minutes` | Step timeout (default: 360) |
| `shell` | Override default shell |
| `working-directory` | Working directory for `run` commands |

#### Available Shells

| Shell | Command Template | Default On |
|-------|-----------------|------------|
| `bash` | `bash --noprofile --norc -eo pipefail {0}` | Linux/macOS |
| `sh` | `sh -e {0}` | |
| `pwsh` | `pwsh -command ". '{0}'"` | Windows |
| `powershell` | `powershell -command ". '{0}'"` | |
| `cmd` | `cmd /D /E:ON /V:OFF /S /C "CALL "{0}""` | |
| `python` | `python {0}` | |
| Custom | Template string with `{0}` placeholder | |

#### Action References

```yaml
- uses: actions/checkout@v4                    # Version tag
- uses: actions/checkout@a81bbbf8298c0fa03e    # SHA (most secure)
- uses: actions/checkout@main                  # Branch
- uses: actions/aws/ec2@main                   # Subdirectory
- uses: ./.github/actions/my-action            # Local action
- uses: docker://alpine:3.18                   # Docker Hub
- uses: docker://ghcr.io/owner/image:tag       # GHCR
```

---

## 3. Trigger Events

### 3.1 Push and Pull Request Events

#### `push`

Filters: `branches`/`branches-ignore`, `tags`/`tags-ignore`, `paths`/`paths-ignore`

```yaml
on:
  push:
    branches: [main, 'release/**']
    tags: ['v*']
    paths: ['src/**']
    paths-ignore: ['docs/**', '**.md']
```

#### `pull_request`

Default types: `opened`, `synchronize`, `reopened`

All types: `assigned`, `unassigned`, `labeled`, `unlabeled`, `opened`, `edited`, `closed`, `reopened`, `synchronize`, `converted_to_draft`, `locked`, `unlocked`, `enqueued`, `dequeued`, `milestoned`, `demilestoned`, `ready_for_review`, `review_requested`, `review_request_removed`, `auto_merge_enabled`, `auto_merge_disabled`

Runs in context of merge commit. Secrets NOT available for fork PRs.

#### `pull_request_target`

Same types/filters as `pull_request`. Runs in context of **base branch** -- secrets and write permissions available even for fork PRs. Security risk if checking out fork code.

### 3.2 Manual Events

#### `workflow_dispatch`

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options: [staging, production]
      debug:
        type: boolean
        default: false
      version:
        type: string
      log_level:
        type: environment
```

Input types: `string`, `choice`, `boolean`, `number`, `environment`

Access via `${{ inputs.environment }}` or `${{ github.event.inputs.environment }}`.

#### `workflow_call`

Makes workflow reusable. Input types: `boolean`, `number`, `string` (no `choice` or `environment`).

```yaml
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    outputs:
      deploy_url:
        value: ${{ jobs.deploy.outputs.url }}
    secrets:
      api_key:
        required: true
```

#### `workflow_run`

Triggered when another workflow is requested, in_progress, or completed.

```yaml
on:
  workflow_run:
    workflows: [Build, Test]
    types: [completed]
    branches: [main]
```

#### `repository_dispatch`

Custom webhook event triggered via API.

```yaml
on:
  repository_dispatch:
    types: [my-custom-event]
```

### 3.3 Scheduled Events

```yaml
on:
  schedule:
    - cron: '30 5 * * 1,3'   # 5:30 UTC Mon and Wed
```

Cron format: `minute hour day-of-month month day-of-week`. Minimum interval: 5 minutes. Runs on default branch.

### 3.4 All Webhook Events

| Event | Activity Types |
|-------|---------------|
| `branch_protection_rule` | `created`, `edited`, `deleted` |
| `check_run` | `created`, `rerequested`, `completed`, `requested_action` |
| `check_suite` | `completed` |
| `create` | (none) -- branch/tag created |
| `delete` | (none) -- branch/tag deleted |
| `deployment` | (none) |
| `deployment_status` | (none) |
| `discussion` | `created`, `edited`, `deleted`, `transferred`, `pinned`, `unpinned`, `labeled`, `unlabeled`, `locked`, `unlocked`, `category_changed`, `answered`, `unanswered` |
| `discussion_comment` | `created`, `edited`, `deleted` |
| `fork` | (none) |
| `gollum` | (none) -- wiki page created/updated |
| `issue_comment` | `created`, `edited`, `deleted` |
| `issues` | `opened`, `edited`, `deleted`, `transferred`, `pinned`, `unpinned`, `closed`, `reopened`, `assigned`, `unassigned`, `labeled`, `unlabeled`, `locked`, `unlocked`, `milestoned`, `demilestoned` |
| `label` | `created`, `edited`, `deleted` |
| `merge_group` | `checks_requested` |
| `milestone` | `created`, `closed`, `opened`, `edited`, `deleted` |
| `page_build` | (none) |
| `project` | `created`, `closed`, `reopened`, `edited`, `deleted` |
| `project_card` | `created`, `moved`, `converted`, `edited`, `deleted` |
| `project_column` | `created`, `updated`, `moved`, `deleted` |
| `public` | (none) -- repo goes public |
| `registry_package` | `published`, `updated` |
| `release` | `published`, `unpublished`, `created`, `edited`, `deleted`, `prereleased`, `released` |
| `status` | (none) -- commit status changes |
| `watch` | `started` -- someone stars the repo |

### 3.5 Filter Patterns

Used in `branches`, `branches-ignore`, `tags`, `tags-ignore`, `paths`, `paths-ignore`:

| Pattern | Description |
|---------|-------------|
| `*` | Matches any character except `/` |
| `**` | Matches any character including `/` |
| `?` | Matches a single character |
| `[abc]` | Character set |
| `[a-z]` | Character range |
| `!` | Negation (in paths) |

`branches`/`branches-ignore` are mutually exclusive. Same for `tags`/`tags-ignore` and `paths`/`paths-ignore`.

---

## 4. Expression Syntax

Expressions are wrapped in `${{ <expression> }}`. In `if` conditions, the `${{ }}` wrapper is optional.

### 4.1 Literals

| Type | Examples |
|------|----------|
| Boolean | `true`, `false` |
| Null | `null` |
| Number | `0`, `3.14`, `-1`, `0xff`, `1.2e5`, `NaN`, `Infinity` |
| String | `'single quotes'` (double quotes NOT valid in expressions) |

### 4.2 Operators

| Operator | Description |
|----------|-------------|
| `()` | Logical grouping |
| `[]` | Index/property access |
| `.` | Property dereference |
| `!` | Logical NOT |
| `<`, `<=`, `>`, `>=` | Comparison |
| `==`, `!=` | Equality (loose type coercion) |
| `&&` | Logical AND |
| `||` | Logical OR (short-circuit) |

Type coercion for `==`: Null -> `0`/`''`/`false`; Boolean -> `1`/`0`; String -> parsed as number if possible.

### 4.3 Built-in Functions

| Function | Description |
|----------|-------------|
| `contains(search, item)` | Case-insensitive substring/array membership |
| `startsWith(str, value)` | Case-insensitive prefix check |
| `endsWith(str, value)` | Case-insensitive suffix check |
| `format(str, val0, ...)` | Replace `{0}`, `{1}`, etc. |
| `join(array, separator)` | Concatenate array elements (default: `,`) |
| `toJSON(value)` | Pretty-print as JSON |
| `fromJSON(value)` | Parse JSON string into value |
| `hashFiles(path, ...)` | SHA-256 hash of matching files |

### 4.4 Status Check Functions

| Function | Description |
|----------|-------------|
| `success()` | All previous steps/jobs succeeded (implicit default) |
| `always()` | Always `true`, even if cancelled |
| `failure()` | Any previous step/job failed |
| `cancelled()` | Workflow was cancelled |

### 4.5 Object Filter Syntax

```yaml
${{ github.event.issue.labels.*.name }}   # Returns array of label names
${{ github.event.issue.labels[0].name }}  # Index access
```

---

## 5. Contexts

### 5.1 `github` Context

| Property | Description |
|----------|-------------|
| `github.action` | Current action name or step ID |
| `github.action_path` | Path where action is located |
| `github.action_ref` | Action ref (e.g., `v4`) |
| `github.action_repository` | Action repo (e.g., `actions/checkout`) |
| `github.actor` | Username that triggered the run |
| `github.actor_id` | Account ID |
| `github.api_url` | API URL (e.g., `https://api.github.com`) |
| `github.base_ref` | PR base branch |
| `github.env` | Path to `$GITHUB_ENV` file |
| `github.event` | Full webhook payload object |
| `github.event_name` | Event name (e.g., `push`) |
| `github.event_path` | Path to event payload JSON file |
| `github.graphql_url` | GraphQL API URL |
| `github.head_ref` | PR head branch |
| `github.job` | Current job ID |
| `github.output` | Path to `$GITHUB_OUTPUT` file |
| `github.path` | Path to `$GITHUB_PATH` file |
| `github.ref` | Full ref (e.g., `refs/heads/main`) |
| `github.ref_name` | Short ref name (e.g., `main`) |
| `github.ref_protected` | Boolean: branch protection enabled |
| `github.ref_type` | `branch` or `tag` |
| `github.repository` | `owner/repo` |
| `github.repository_id` | Numeric repo ID |
| `github.repository_owner` | Owner name |
| `github.repository_owner_id` | Owner account ID |
| `github.repositoryUrl` | Git URL |
| `github.retention_days` | Artifact retention days |
| `github.run_id` | Unique numeric run ID |
| `github.run_number` | Sequential run number for this workflow |
| `github.run_attempt` | Re-run attempt number (starts at 1) |
| `github.secret_source` | `Actions`, `Codespaces`, or `Dependabot` |
| `github.server_url` | GitHub server URL |
| `github.sha` | Commit SHA |
| `github.token` | GITHUB_TOKEN |
| `github.triggering_actor` | User who triggered re-run |
| `github.workflow` | Workflow name |
| `github.workflow_ref` | Full workflow file ref path |
| `github.workflow_sha` | Workflow file commit SHA |
| `github.workspace` | Working directory on runner |

### 5.2 Other Contexts

| Context | Key Properties |
|---------|---------------|
| `env` | `env.MY_VAR` -- environment variables |
| `vars` | `vars.MY_CONFIG` -- configuration variables |
| `job` | `job.status`, `job.container.id`, `job.container.network`, `job.services.<id>.id`, `job.services.<id>.ports` |
| `jobs` | `jobs.<id>.result`, `jobs.<id>.outputs.<name>` (reusable workflows only) |
| `steps` | `steps.<id>.outputs.<name>`, `steps.<id>.outcome`, `steps.<id>.conclusion` |
| `runner` | `runner.name`, `runner.os`, `runner.arch`, `runner.temp`, `runner.tool_cache`, `runner.debug`, `runner.environment` |
| `secrets` | `secrets.MY_SECRET`, `secrets.GITHUB_TOKEN` |
| `strategy` | `strategy.fail-fast`, `strategy.job-index`, `strategy.job-total`, `strategy.max-parallel` |
| `matrix` | `matrix.<var>` -- current matrix values |
| `needs` | `needs.<job>.result`, `needs.<job>.outputs.<name>` |
| `inputs` | `inputs.<name>` -- from `workflow_dispatch` or `workflow_call` |

`outcome` vs `conclusion`: If a step has `continue-on-error: true` and fails, `outcome` is `failure` but `conclusion` is `success`.

---

## 6. Matrix Strategies

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    node: [18, 20]
    include:
      - os: ubuntu-latest
        node: 21
        experimental: true
    exclude:
      - os: windows-latest
        node: 18
  fail-fast: true        # default: true
  max-parallel: 3        # max concurrent matrix jobs
```

- `matrix`: Defines variables; creates Cartesian product of all combinations
- `include`: Add combinations or merge extra properties into existing ones
- `exclude`: Remove specific combinations
- `fail-fast`: Cancel all matrix jobs on first failure (default: `true`)
- `max-parallel`: Limit concurrent matrix jobs

### Dynamic Matrices with `fromJSON`

```yaml
jobs:
  setup:
    outputs:
      matrix: ${{ steps.set.outputs.matrix }}
    steps:
      - id: set
        run: echo 'matrix={"os":["ubuntu-latest"],"node":[18,20]}' >> $GITHUB_OUTPUT
  test:
    needs: setup
    strategy:
      matrix: ${{ fromJSON(needs.setup.outputs.matrix) }}
```

---

## 7. Conditionals

```yaml
# Job-level
jobs:
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

# Step-level
steps:
  - if: failure()
    run: ./notify.sh
  - if: always()
    run: ./cleanup.sh
  - if: "!cancelled()"
    run: echo "Not cancelled"
  - if: success() || failure()
    run: echo "Runs unless cancelled"

# With needs
jobs:
  notify:
    needs: build
    if: always()  # runs even if build failed
  deploy:
    needs: [build, test]
    if: needs.build.result == 'success' && needs.test.result == 'success'
```

Negation with `!` must be quoted: `if: "!startsWith(github.ref, 'refs/tags/')"`

---

## 8. REST API Endpoints

All endpoints under `https://api.github.com`. Authentication via `Authorization: Bearer <token>`.

### 8.1 Workflows (5 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/workflows` | List workflows |
| `GET` | `/repos/{owner}/{repo}/actions/workflows/{id}` | Get workflow (ID or filename) |
| `PUT` | `/repos/{owner}/{repo}/actions/workflows/{id}/disable` | Disable workflow |
| `PUT` | `/repos/{owner}/{repo}/actions/workflows/{id}/enable` | Enable workflow |
| `POST` | `/repos/{owner}/{repo}/actions/workflows/{id}/dispatches` | Trigger workflow_dispatch |

Dispatch body: `{ ref: "main", inputs: { key: "value" } }`

### 8.2 Workflow Runs (18 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/runs` | List runs (filters: `actor`, `branch`, `event`, `status`, `created`, `head_sha`) |
| `GET` | `/repos/{owner}/{repo}/actions/workflows/{id}/runs` | List runs for workflow |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}` | Get run |
| `DELETE` | `/repos/{owner}/{repo}/actions/runs/{run_id}` | Delete run |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/timing` | Get run usage/billing |
| `POST` | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun` | Re-run all jobs |
| `POST` | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs` | Re-run failed jobs |
| `POST` | `/repos/{owner}/{repo}/actions/runs/{run_id}/cancel` | Cancel run |
| `POST` | `/repos/{owner}/{repo}/actions/runs/{run_id}/force-cancel` | Force cancel run |
| `POST` | `/repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` | Review pending deployments |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` | Get pending deployments |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts` | List run artifacts |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` | Download run logs (302 redirect) |
| `DELETE` | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` | Delete run logs |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{n}` | Get run attempt |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{n}/jobs` | List jobs for attempt |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{n}/logs` | Download attempt logs |
| `POST` | `/repos/{owner}/{repo}/actions/runs/{run_id}/approve` | Approve fork PR run |

#### Workflow Run Object

Key fields: `id`, `name`, `node_id`, `head_branch`, `head_sha`, `path`, `display_title`, `run_number`, `run_attempt`, `event`, `status`, `conclusion`, `workflow_id`, `check_suite_id`, `url`, `html_url`, `pull_requests[]`, `created_at`, `updated_at`, `actor`, `triggering_actor`, `run_started_at`, `jobs_url`, `logs_url`, `artifacts_url`, `head_commit`, `repository`, `head_repository`, `referenced_workflows[]`

Status values: `completed`, `action_required`, `cancelled`, `failure`, `neutral`, `skipped`, `stale`, `success`, `timed_out`, `in_progress`, `queued`, `requested`, `waiting`, `pending`

### 8.3 Workflow Jobs (4 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | List jobs (filter: `latest` or `all`) |
| `GET` | `/repos/{owner}/{repo}/actions/jobs/{job_id}` | Get job |
| `GET` | `/repos/{owner}/{repo}/actions/jobs/{job_id}/logs` | Download job logs (302 redirect) |
| `POST` | `/repos/{owner}/{repo}/actions/jobs/{job_id}/rerun` | Re-run specific job |

#### Job Object

Key fields: `id`, `run_id`, `run_attempt`, `node_id`, `head_sha`, `status`, `conclusion`, `created_at`, `started_at`, `completed_at`, `name`, `steps[]`, `labels[]`, `runner_id`, `runner_name`, `runner_group_id`, `runner_group_name`, `workflow_name`

Step fields: `name`, `status`, `conclusion`, `number`, `started_at`, `completed_at`

### 8.4 Artifacts (5 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/artifacts` | List repo artifacts |
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts` | List run artifacts |
| `GET` | `/repos/{owner}/{repo}/actions/artifacts/{id}` | Get artifact |
| `DELETE` | `/repos/{owner}/{repo}/actions/artifacts/{id}` | Delete artifact |
| `GET` | `/repos/{owner}/{repo}/actions/artifacts/{id}/{format}` | Download artifact (302; format=`zip`) |

Artifact fields: `id`, `node_id`, `name`, `size_in_bytes`, `url`, `archive_download_url`, `expired`, `created_at`, `updated_at`, `expires_at`, `workflow_run`

### 8.5 Secrets (15 endpoints)

#### Repository Secrets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/secrets` | List secrets |
| `GET` | `/repos/{owner}/{repo}/actions/secrets/{name}` | Get secret metadata |
| `PUT` | `/repos/{owner}/{repo}/actions/secrets/{name}` | Create/update secret |
| `DELETE` | `/repos/{owner}/{repo}/actions/secrets/{name}` | Delete secret |
| `GET` | `/repos/{owner}/{repo}/actions/secrets/public-key` | Get public key for encryption |

Secret creation body: `{ encrypted_value: "<LibSodium sealed box>", key_id: "<public key ID>" }`

Public key response: `{ key_id, key }` (Base64-encoded X25519 public key)

#### Organization Secrets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/orgs/{org}/actions/secrets` | List org secrets |
| `GET` | `/orgs/{org}/actions/secrets/{name}` | Get org secret |
| `PUT` | `/orgs/{org}/actions/secrets/{name}` | Create/update (with `visibility`: `all`/`private`/`selected`) |
| `DELETE` | `/orgs/{org}/actions/secrets/{name}` | Delete |
| `GET` | `/orgs/{org}/actions/secrets/public-key` | Get org public key |
| `GET` | `/orgs/{org}/actions/secrets/{name}/repositories` | List repos with access |
| `PUT` | `/orgs/{org}/actions/secrets/{name}/repositories` | Set repo access |
| `PUT` | `/orgs/{org}/actions/secrets/{name}/repositories/{repo_id}` | Add repo access |
| `DELETE` | `/orgs/{org}/actions/secrets/{name}/repositories/{repo_id}` | Remove repo access |

#### Environment Secrets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/environments/{env}/secrets` | List |
| `GET` | `/repos/{owner}/{repo}/environments/{env}/secrets/{name}` | Get |
| `PUT` | `/repos/{owner}/{repo}/environments/{env}/secrets/{name}` | Create/update |
| `DELETE` | `/repos/{owner}/{repo}/environments/{env}/secrets/{name}` | Delete |
| `GET` | `/repos/{owner}/{repo}/environments/{env}/secrets/public-key` | Get public key |

### 8.6 Variables (15 endpoints)

Same structure as secrets but at repository, organization, and environment levels. Variable objects include `name`, `value`, `created_at`, `updated_at`. Organization variables add `visibility` and `selected_repositories_url`.

| Scope | List | Get | Create | Update | Delete |
|-------|------|-----|--------|--------|--------|
| Repo | `GET .../actions/variables` | `GET .../variables/{name}` | `POST .../variables` | `PATCH .../variables/{name}` | `DELETE .../variables/{name}` |
| Org | `GET /orgs/{org}/actions/variables` | Same pattern | Same | Same | Same |
| Env | `GET .../environments/{env}/variables` | Same pattern | Same | Same | Same |

### 8.7 Self-Hosted Runners (18 endpoints)

#### Repository Runners

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/runners` | List runners |
| `GET` | `/repos/{owner}/{repo}/actions/runners/{id}` | Get runner |
| `DELETE` | `/repos/{owner}/{repo}/actions/runners/{id}` | Delete runner |
| `GET` | `/repos/{owner}/{repo}/actions/runners/downloads` | List runner binaries |
| `POST` | `/repos/{owner}/{repo}/actions/runners/registration-token` | Create registration token |
| `POST` | `/repos/{owner}/{repo}/actions/runners/remove-token` | Create removal token |

Runner object: `id`, `name`, `os`, `status` (`online`/`offline`), `busy` (boolean), `labels[]` (each with `id`, `name`, `type`: `read-only`/`custom`)

Registration token response: `{ token, expires_at }` (valid 1 hour)

#### Runner Labels

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `.../runners/{id}/labels` | List labels |
| `POST` | `.../runners/{id}/labels` | Add custom labels |
| `PUT` | `.../runners/{id}/labels` | Replace all custom labels |
| `DELETE` | `.../runners/{id}/labels` | Remove all custom labels |
| `DELETE` | `.../runners/{id}/labels/{name}` | Remove specific label |

Same endpoints exist at organization level (`/orgs/{org}/actions/runners/...`).

#### JIT (Just-In-Time) Runners

```
POST /repos/{owner}/{repo}/actions/runners/generate-jitconfig
```

Request: `{ name, runner_group_id, labels: ["self-hosted", "linux"], work_folder: "_work" }`

Response includes `encoded_jit_config` (base64). Runner starts with `./run.sh --jitconfig {config}` -- automatically ephemeral.

### 8.8 Runner Groups (11 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/orgs/{org}/actions/runner-groups` | List groups |
| `GET` | `/orgs/{org}/actions/runner-groups/{id}` | Get group |
| `POST` | `/orgs/{org}/actions/runner-groups` | Create group |
| `PATCH` | `/orgs/{org}/actions/runner-groups/{id}` | Update group |
| `DELETE` | `/orgs/{org}/actions/runner-groups/{id}` | Delete group |
| `GET` | `/orgs/{org}/actions/runner-groups/{id}/repositories` | List repo access |
| `PUT` | `/orgs/{org}/actions/runner-groups/{id}/repositories` | Set repo access |
| `PUT` | `/orgs/{org}/actions/runner-groups/{id}/repositories/{repo_id}` | Add repo |
| `DELETE` | `/orgs/{org}/actions/runner-groups/{id}/repositories/{repo_id}` | Remove repo |
| `GET` | `/orgs/{org}/actions/runner-groups/{id}/runners` | List runners in group |
| `PUT` | `/orgs/{org}/actions/runner-groups/{id}/runners/{runner_id}` | Add runner to group |
| `DELETE` | `/orgs/{org}/actions/runner-groups/{id}/runners/{runner_id}` | Remove runner |

Group fields: `id`, `name`, `visibility` (`all`/`selected`/`private`), `default`, `allows_public_repositories`, `restricted_to_workflows`, `selected_workflows[]`

### 8.9 Permissions (14 endpoints)

#### Organization Permissions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/orgs/{org}/actions/permissions` | Get org Actions permissions |
| `PUT` | `/orgs/{org}/actions/permissions` | Set (`enabled_repositories`: `all`/`none`/`selected`) |
| `GET` | `/orgs/{org}/actions/permissions/repositories` | List enabled repos |
| `PUT` | `/orgs/{org}/actions/permissions/repositories` | Set enabled repos |
| `PUT` | `/orgs/{org}/actions/permissions/repositories/{id}` | Enable repo |
| `DELETE` | `/orgs/{org}/actions/permissions/repositories/{id}` | Disable repo |
| `GET` | `/orgs/{org}/actions/permissions/selected-actions` | Get allowed actions |
| `PUT` | `/orgs/{org}/actions/permissions/selected-actions` | Set allowed actions |
| `GET` | `/orgs/{org}/actions/permissions/workflow` | Get default workflow permissions |
| `PUT` | `/orgs/{org}/actions/permissions/workflow` | Set default permissions |

Allowed actions: `{ github_owned_allowed, verified_allowed, patterns_allowed[] }`

Default workflow permissions: `{ default_workflow_permissions: "read"/"write", can_approve_pull_request_reviews }`

#### Repository Permissions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/permissions` | Get repo permissions |
| `PUT` | `/repos/{owner}/{repo}/actions/permissions` | Set (`enabled`, `allowed_actions`) |
| `GET/PUT` | `.../permissions/selected-actions` | Get/set allowed actions |
| `GET/PUT` | `.../permissions/workflow` | Get/set default workflow permissions |
| `GET/PUT` | `.../permissions/access` | Get/set external workflow access (`none`/`user`/`organization`) |

### 8.10 Cache (6 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/cache/usage` | Get cache usage |
| `GET` | `/repos/{owner}/{repo}/actions/caches` | List caches (filter: `ref`, `key`, `sort`) |
| `DELETE` | `/repos/{owner}/{repo}/actions/caches?key={prefix}` | Delete by key prefix |
| `DELETE` | `/repos/{owner}/{repo}/actions/caches/{id}` | Delete by ID |
| `GET` | `/orgs/{org}/actions/cache/usage` | Get org cache usage |
| `GET` | `/orgs/{org}/actions/cache/usage-by-repository` | Cache usage per repo |

Cache fields: `id`, `ref`, `key`, `version`, `last_accessed_at`, `created_at`, `size_in_bytes`

### 8.11 OIDC (4 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/oidc/customization/sub` | Get OIDC subject template |
| `PUT` | `/repos/{owner}/{repo}/actions/oidc/customization/sub` | Set OIDC subject template |
| `GET` | `/orgs/{org}/actions/oidc/customization/sub` | Get org OIDC template |
| `PUT` | `/orgs/{org}/actions/oidc/customization/sub` | Set org OIDC template |

Body: `{ use_default, include_claim_keys: ["repo", "context", "actor", ...] }`

### 8.12 Additional Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/actions/runs/{run_id}/approvals` | Get review history |
| `GET` | `/orgs/{org}/actions/required_workflows` | List required workflows |
| `POST` | `/orgs/{org}/actions/required_workflows` | Create required workflow |
| `PATCH` | `/orgs/{org}/actions/required_workflows/{id}` | Update |
| `DELETE` | `/orgs/{org}/actions/required_workflows/{id}` | Delete |

### 8.13 Endpoint Count Summary

| Category | Count |
|----------|-------|
| Workflows | 5 |
| Workflow Runs | 18 |
| Workflow Jobs | 4 |
| Artifacts | 5 |
| Secrets (repo + org + env) | 15 |
| Variables (repo + org + env) | 15 |
| Self-Hosted Runners (repo + org + labels) | 18 |
| Runner Groups | 11 |
| Permissions (org + repo) | 14 |
| Cache | 6 |
| OIDC | 4 |
| Additional | 9 |
| **Total** | **~124** |

### 8.14 Common API Patterns

**Pagination**: All list endpoints support `per_page` (default 30, max 100) and `page`. Response includes `Link` header with `rel="next"`, `rel="prev"`, `rel="first"`, `rel="last"`.

**Rate Limiting**: Headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

**Authentication**: `Authorization: token <PAT>`, `Authorization: Bearer <fine-grained-PAT>`, or GitHub App installation token. Scopes: `repo`, `admin:org`, `workflow`.

---

## 9. Runner Protocol & Architecture

### 9.1 Source Repository

The runner is open source at **https://github.com/actions/runner**, written in C# (.NET 6+).

### 9.2 Component Architecture

```
src/
  Runner.Common/           # Shared utilities, logging, config
    Authentication/        # RSA key handling, OAuth token exchange
    BrokerHttpClient.cs    # Actions Broker HTTP client
    ConfigurationStore.cs  # .runner, .credentials file management
    Constants.cs           # API versions, URLs, defaults
    HostContext.cs          # DI container
    RunnerServer.cs        # Actions service API client

  Runner.Listener/         # Main daemon process
    Configuration/
      ConfigurationManager.cs  # Registration/removal flow
      CredentialManager.cs     # RSA key generation
    BrokerMessageListener.cs   # Long-poll (newer broker protocol)
    MessageListener.cs         # Long-poll (legacy protocol)
    JobDispatcher.cs           # Spawn/manage Worker processes
    Runner.cs                  # Main orchestration loop
    SelfUpdater.cs             # Auto-update handler

  Runner.Worker/           # Per-job child process
    ActionManager.cs       # Download/cache actions
    ActionRunner.cs        # Execute individual actions
    Container/             # Docker container management
    ExecutionContext.cs     # Job/step state management
    Handlers/
      CompositeActionHandler.cs
      ContainerActionHandler.cs
      NodeScriptActionHandler.cs
      ScriptHandler.cs     # run: steps
    StepsRunner.cs         # Step orchestration
    Worker.cs              # Entry point

  Runner.Plugins/          # Built-in plugins
    BuildArtifact/         # Upload/download artifacts
    Repository/            # actions/checkout

  Runner.Sdk/              # API contracts, types
    Pipeline/              # Workflow YAML parsing
```

### 9.3 Process Model

```
                    +-----------------+
                    | Runner.Listener |  (long-lived daemon)
                    | - MessageListener|
                    | - JobDispatcher  |
                    +--------+--------+
                             |
                     spawns child process per job
                             |
                    +--------v--------+
                    |  Runner.Worker  |  (one per concurrent job)
                    | - StepsRunner   |
                    | - ActionRunner  |
                    +-----------------+
```

- Listener is the long-running process (service or foreground)
- Each job gets its own Worker **process** (not thread) for isolation
- Worker communicates to Listener via named pipes / local IPC
- Worker directly communicates with Actions service for log uploads (gets its own OAuth token)

---

## 10. Runner Registration & Authentication

### 10.1 Registration Flow

**Phase 1**: Obtain registration token via REST API:
```
POST /repos/{owner}/{repo}/actions/runners/registration-token
```
Response: `{ token: "AABBORZ...", expires_at: "..." }` (valid 1 hour)

**Phase 2**: Run `./config.sh --url https://github.com/{owner}/{repo} --token AABBORZ...`

The runner:
1. Parses URL to determine scope (repo/org/enterprise)
2. Generates RSA 2048-bit key pair
3. Calls `POST /_apis/distributedtask/pools/{poolId}/agents` on `pipelines.actions.githubusercontent.com` with: runner name, version, OS, architecture, labels, RSA public key
4. Receives: agent ID, OAuth credentials, server URL

### 10.2 Credential Files

| File | Contents |
|------|----------|
| `.runner` | JSON: agent ID, pool ID, runner name, server URL, runner group |
| `.credentials` | JSON: OAuth scheme, client ID, authorization URL |
| `.credentials_rsaparams` | JSON: RSA private key parameters (d, dp, dq, exponent, inverseQ, modulus, p, q) |

### 10.3 Ongoing Authentication

After registration, the runner **never uses the registration token again**. For every API call:

1. Constructs JWT with agent ID, pool ID, short expiration (~10 min)
2. Signs JWT with local RSA private key
3. Exchanges JWT at authorization URL for short-lived OAuth access token
4. Uses access token as Bearer token for API calls

### 10.4 Deregistration

```bash
./config.sh remove --token {removal-token}
```

Calls `DELETE /_apis/distributedtask/pools/{poolId}/agents/{agentId}` and deletes local credential files.

---

## 11. Job Dispatch & Execution Lifecycle

### 11.1 Communication Protocol

**Legacy protocol** (`MessageListener.cs`): HTTP long-polling against `/_apis/distributedtask/` endpoints on `pipelines.actions.githubusercontent.com`.

**Broker protocol** (`BrokerMessageListener.cs`): Newer, more efficient. Broker sits between runner and backend; better scalability, connection multiplexing. Modern runners (v2.300+) prefer broker.

### 11.2 Session Management

Before polling, runner creates a session:
- `POST /_apis/distributedtask/pools/{poolId}/sessions` with agent ID
- Returns `sessionId` for all subsequent message polling
- Only **one session** per runner at a time
- Periodic keepalives every 30 seconds
- Cleanup: `DELETE .../sessions/{sessionId}`

### 11.3 Job Polling

```
GET /_apis/distributedtask/pools/{poolId}/sessions/{sessionId}/messages?lastMessageId={id}
```

Long poll: server holds connection up to **50 seconds**. Empty response = no work. Runner reconnects immediately with exponential backoff on failure (1s, 2s, 4s, ... up to 30s).

### 11.4 Job Execution

1. **Acceptance**: `POST /_apis/distributedtask/pools/{poolId}/jobrequests/{requestId}` locks the job
2. **Timeline creation**: `POST .../timelines` for live log streaming
3. **Status updates**: `PATCH .../jobrequests/{requestId}` and `PATCH .../timelines/{timelineId}/records`
4. **Log upload**: `POST .../timelines/{timelineId}/logs/{logId}` appends log lines in chunks
5. **Completion**: Final status update with result (`Succeeded`, `Failed`, `Cancelled`)

### 11.5 Internal Actions Service Endpoints

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Register runner | POST | `/_apis/distributedtask/pools/{poolId}/agents` |
| Remove runner | DELETE | `/_apis/distributedtask/pools/{poolId}/agents/{agentId}` |
| Create session | POST | `/_apis/distributedtask/pools/{poolId}/sessions` |
| Delete session | DELETE | `/_apis/distributedtask/pools/{poolId}/sessions/{sessionId}` |
| Poll for messages | GET | `/_apis/distributedtask/pools/{poolId}/sessions/{sessionId}/messages` |
| Update job request | PATCH | `/_apis/distributedtask/pools/{poolId}/jobrequests/{requestId}` |
| Create timeline | POST | `/_apis/distributedtask/pools/{poolId}/timelines` |
| Update timeline | PATCH | `/_apis/distributedtask/pools/{poolId}/timelines/{timelineId}/records` |
| Upload logs | POST | `/_apis/distributedtask/pools/{poolId}/timelines/{timelineId}/logs/{logId}` |

Base URL: `https://pipelines.actions.githubusercontent.com/{scope_identifier}` where `scope_identifier` is a GUID.

### 11.6 Key Constants

| Parameter | Value |
|-----------|-------|
| Long poll timeout | 50 seconds |
| Session keepalive | Every 30 seconds |
| OAuth token lifetime | ~10 minutes |
| Registration token lifetime | 1 hour |
| Max job runtime (GitHub.com) | 6 hours |
| Max job runtime (self-hosted) | 72 hours |
| Reconnect backoff | 1s, 2s, 4s, ... up to 30s |

### 11.7 Network Requirements (Outbound HTTPS 443)

| Host | Purpose |
|------|---------|
| `github.com` | API calls |
| `api.github.com` | REST API |
| `*.actions.githubusercontent.com` | Actions service |
| `pipelines.actions.githubusercontent.com` | Primary backend |
| `codeload.github.com` | Repo archive downloads |
| `ghcr.io`, `*.ghcr.io` | Container Registry |
| `*.blob.core.windows.net` | Azure blob (caches, artifacts) |
| `results-receiver.actions.githubusercontent.com` | Results service |

No inbound ports required.

---

## 12. Environments

### 12.1 Overview

Environments describe deployment targets (e.g., `production`, `staging`). Jobs reference via the `environment` key. GitHub creates deployment records.

```yaml
jobs:
  deploy:
    environment:
      name: production
      url: ${{ steps.deploy.outputs.url }}
```

### 12.2 Protection Rules

- **Required Reviewers**: Up to 6 people/teams; one approval needed; 30-day timeout
- **Wait Timer**: 0-43,200 minutes delay after approval
- **Deployment Branches/Tags**: Restrict which refs can deploy (all, protected, or selected with wildcards)
- **Custom Protection Rules**: Third-party services approve/reject via Deployments API (Enterprise)

### 12.3 Environment Secrets & Variables

- Override repo-level secrets/variables with same name
- Precedence: Environment > Repository > Organization
- Only available to jobs referencing that environment

### 12.4 API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repos/{owner}/{repo}/environments` | List environments |
| `GET` | `/repos/{owner}/{repo}/environments/{name}` | Get environment |
| `PUT` | `/repos/{owner}/{repo}/environments/{name}` | Create/update |
| `DELETE` | `/repos/{owner}/{repo}/environments/{name}` | Delete |

---

## 13. Secrets

### 13.1 Types

- **Organization secrets**: Shared across repos (visibility: `all`/`private`/`selected`)
- **Repository secrets**: Per-repo
- **Environment secrets**: Per-environment; override repo secrets

### 13.2 Limits

- Organization: 1,000 max
- Repository: 100 max
- Environment: 100 max
- Value size: 48 KB max
- Names: alphanumeric + underscores, cannot start with `GITHUB_`, case-insensitive

### 13.3 Encryption

Secrets are encrypted using LibSodium sealed boxes with an X25519 public key. To create/update a secret:

1. `GET .../secrets/public-key` to get `{ key_id, key }`
2. Encrypt value with the public key
3. `PUT .../secrets/{name}` with `{ encrypted_value, key_id }`

### 13.4 Redaction

- Automatically masked in logs with `***`
- Structured data (JSON) may not be fully redacted
- Use `::add-mask::` for additional masking

### 13.5 Fork Behavior

Secrets are NOT available for `pull_request` from forks (except `GITHUB_TOKEN`). `pull_request_target` has access to base repo secrets.

---

## 14. Variables

Non-sensitive configuration values. Same scoping as secrets (org/repo/environment). Same precedence: Environment > Repository > Organization.

Accessed via `${{ vars.MY_CONFIG }}`.

---

## 15. Artifacts

### 15.1 Upload/Download

```yaml
# Upload
- uses: actions/upload-artifact@v4
  with:
    name: build-output
    path: dist/
    retention-days: 5
    if-no-files-found: error  # 'warn' (default), 'error', 'ignore'
    compression-level: 6      # 0-9

# Download
- uses: actions/download-artifact@v4
  with:
    name: build-output
    path: ./dist
```

### 15.2 Retention

- Default: 90 days (configurable 1-400 for public repos, 1-90 for free private repos)
- Organization default overrides (repos can only reduce)
- Artifacts v4: immutable names, no overwriting

---

## 16. Caching

### 16.1 Usage

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-node-
```

### 16.2 Scope

- Scoped to repository and branch
- Feature branches can access default branch caches
- Default branch can only access its own caches
- PRs can access base and head branch caches
- No cross-repo caching

### 16.3 Limits

- **10 GB per repository** total
- LRU eviction when exceeded
- Caches not accessed in **7 days** auto-evicted
- Key max length: 512 characters

### 16.4 Split Actions

- `actions/cache/restore@v4` -- restore only (no save)
- `actions/cache/save@v4` -- save only (explicit save points)

---

## 17. Concurrency

```yaml
# Workflow level
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

# Job level
jobs:
  deploy:
    concurrency:
      group: deploy-production
      cancel-in-progress: false
```

- Only one run/job per concurrency group at a time
- `cancel-in-progress: true`: new run cancels currently running one
- `cancel-in-progress: false` (default): new run queues behind current
- Max one pending + one running per group

---

## 18. GITHUB_TOKEN & Permissions

### 18.1 Overview

- Automatically created per workflow run
- Accessed via `secrets.GITHUB_TOKEN` or `github.token`
- Expires when run completes (or after 24 hours)
- Scoped to the single repository

### 18.2 Permission Scopes

| Scope | Values | Description |
|-------|--------|-------------|
| `actions` | read/write/none | Manage Actions |
| `attestations` | read/write/none | Artifact attestations |
| `checks` | read/write/none | Check runs/suites |
| `contents` | read/write/none | Repo contents, commits, branches, releases |
| `deployments` | read/write/none | Deployments |
| `discussions` | read/write/none | Discussions |
| `id-token` | write/none | OIDC JWT tokens |
| `issues` | read/write/none | Issues |
| `packages` | read/write/none | GitHub Packages |
| `pages` | read/write/none | GitHub Pages |
| `pull-requests` | read/write/none | Pull requests |
| `repository-projects` | read/write/none | Projects |
| `security-events` | read/write/none | Code scanning, Dependabot |
| `statuses` | read/write/none | Commit statuses |

### 18.3 Behavior

- Setting ANY permission explicitly causes all unspecified to default to `none`
- Exception: `metadata` is always `read`
- Job-level permissions override (not merge) workflow-level
- `permissions: {}` = no permissions; `permissions: read-all` = all read; `permissions: write-all` = all write
- Fork PRs always get read-only GITHUB_TOKEN

---

## 19. Service Containers

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
```

Properties per service: `image`, `credentials`, `env`, `ports`, `volumes`, `options`

Networking:
- **Without job container**: access via `localhost` + mapped port
- **With job container**: access via service name as hostname (e.g., `postgres`), shared Docker network

---

## 20. Job Containers

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: node:20
      credentials:
        username: ${{ github.actor }}
        password: ${{ secrets.GHCR_TOKEN }}
      env:
        NODE_ENV: test
      ports:
        - 80
      volumes:
        - /src:/container/src
      options: --cpus 1 --memory 4g
```

Short form: `container: node:20`

- Runner mounts workspace into container
- `actions/checkout` works inside containers
- JavaScript actions run on the runner host (not in container)
- Linux runners only

---

## 21. Workflow Commands

Commands written to stdout or environment files that the runner interprets.

### 21.1 Environment Files

```bash
# Set output (via $GITHUB_OUTPUT)
echo "name=value" >> "$GITHUB_OUTPUT"

# Multiline output
echo "name<<EOF" >> "$GITHUB_OUTPUT"
echo "content" >> "$GITHUB_OUTPUT"
echo "EOF" >> "$GITHUB_OUTPUT"

# Set environment variable (via $GITHUB_ENV)
echo "MY_VAR=value" >> "$GITHUB_ENV"

# Add to PATH (via $GITHUB_PATH)
echo "/my/path" >> "$GITHUB_PATH"

# Step summary (via $GITHUB_STEP_SUMMARY) -- supports Markdown
echo "### Build Results" >> "$GITHUB_STEP_SUMMARY"

# Save state (via $GITHUB_STATE) -- for pre/main/post action communication
echo "key=value" >> "$GITHUB_STATE"
```

### 21.2 Stdout Commands

```bash
# Annotations
echo "::error file=app.js,line=10,col=5,endLine=12,endColumn=8,title=Syntax Error::Message"
echo "::warning file=app.js,line=10::Deprecated function"
echo "::notice::Build completed"

# Debug (only shown with debug logging enabled)
echo "::debug::Detailed info"

# Log grouping
echo "::group::Section Name"
echo "content"
echo "::endgroup::"

# Mask value in logs
echo "::add-mask::sensitive-value"

# Stop/start command processing
echo "::stop-commands::TOKEN"
echo "not processed as command"
echo "::TOKEN::"
```

### 21.3 Step Summary Limits

- 1 MB per step
- 20 MB per job

---

## 22. Problem Matchers

JSON configuration files that define regex patterns to scan log output and create annotations.

```bash
echo "::add-matcher::path/to/matcher.json"
echo "::remove-matcher owner=name::"
```

Matcher JSON:

```json
{
  "problemMatcher": [{
    "owner": "eslint-compact",
    "pattern": [{
      "regexp": "^(.+):\\s+line\\s+(\\d+),\\s+col\\s+(\\d+),\\s+(Error|Warning)\\s+-\\s+(.+)$",
      "file": 1, "line": 2, "column": 3, "severity": 4, "message": 5
    }]
  }]
}
```

Pattern fields: `regexp`, `file`, `line`, `column`, `endLine`, `endColumn`, `severity`, `message`, `code`

Multi-line: array of patterns; consecutive lines must match; last pattern must contain `message`.

---

## 23. Custom Actions

### 23.1 Action Types

| Type | Language | Platforms | `using` Value |
|------|----------|-----------|---------------|
| JavaScript | Node.js | Linux, macOS, Windows | `node12`, `node16`, `node20` |
| Composite | Mixed | All | `composite` |
| Docker | Any | Linux only | `docker` |

### 23.2 `action.yml` Metadata

```yaml
name: 'My Action'
description: 'Does something useful'
author: 'Your Name'

branding:
  icon: 'check-circle'
  color: 'green'

inputs:
  name:
    description: 'Input description'
    required: true
    default: 'World'
    deprecationMessage: 'Use something else'

outputs:
  result:
    description: 'Output description'
    value: ${{ steps.run.outputs.result }}  # composite only

runs:
  # JavaScript
  using: 'node20'
  main: 'dist/index.js'
  pre: 'dist/setup.js'
  pre-if: runner.os == 'Linux'
  post: 'dist/cleanup.js'
  post-if: always()

  # Composite
  using: 'composite'
  steps:
    - run: echo "Hello"
      shell: bash   # required for run steps in composite

  # Docker
  using: 'docker'
  image: 'Dockerfile'   # or 'docker://image:tag'
  entrypoint: 'entrypoint.sh'
  pre-entrypoint: 'setup.sh'
  post-entrypoint: 'cleanup.sh'
  args: [${{ inputs.name }}]
  env:
    MY_VAR: value
```

---

## 24. Reusable Workflows

### 24.1 Defining

```yaml
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    outputs:
      url:
        value: ${{ jobs.deploy.outputs.url }}
    secrets:
      key:
        required: true
```

### 24.2 Calling

```yaml
jobs:
  deploy:
    uses: owner/repo/.github/workflows/deploy.yml@main
    with:
      environment: production
    secrets:
      key: ${{ secrets.DEPLOY_KEY }}
    # or: secrets: inherit
```

### 24.3 Limitations

- Max 4 levels of nesting
- Max 20 reusable workflows per file
- Caller `env` NOT propagated to called workflow
- Caller `strategy` NOT passed through
- Private repos: same repo only (unless org settings allow)

---

## 25. OIDC

Enables secretless cloud authentication via workload identity federation.

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/my-role
      aws-region: us-east-1
```

OIDC subject claim customization: `{ use_default, include_claim_keys: ["repo", "context", "actor", ...] }`

---

## 26. Security Considerations

### 26.1 Self-Hosted Runner Risks

- **Persistent environment**: Files, env vars, credentials persist between jobs
- **Cross-job data leakage**: Subsequent jobs can access prior job artifacts
- **Supply chain attacks**: Malicious jobs can install backdoors
- **Fork PR attacks**: Forked PRs can modify workflows to exfiltrate secrets

### 26.2 Best Practices

1. Use **ephemeral runners** (`--ephemeral` flag or JIT config)
2. Dedicated, non-root service account
3. Network isolation (outbound HTTPS 443 only)
4. Never use self-hosted runners on public repos
5. Use runner groups to restrict repo/workflow access
6. Use container isolation (`container:` in workflow)
7. Restrict workflow file changes via `CODEOWNERS`

### 26.3 Secrets Security

- Secrets sent to runner as part of `JobRequestMessage` over HTTPS
- Masked in logs (best-effort pattern match)
- Available as env vars during job -- recoverable from process memory
- Registration token: 1 hour, single-use
- RSA private key (`.credentials_rsaparams`): long-lived identity -- compromise = impersonation

---

## 27. Usage Limits

### 27.1 Execution Limits

| Limit | Value |
|-------|-------|
| Job execution time | 6 hours |
| Workflow run time | 35 days |
| Queue time | 24 hours |
| API requests/hour | 1,000 per repo |
| Concurrent jobs (Free) | 20 |
| Concurrent jobs (Team) | 60 |
| Concurrent jobs (Enterprise) | 500 |
| Matrix max | 256 jobs per run |
| Reusable workflow nesting | 4 levels |
| Variable size | 48 KB |
| Log file size | 64 MB |
| Log storage per run | 2 GB compressed |

### 27.2 Storage

| Plan | Storage | Minutes/month |
|------|---------|---------------|
| Free | 500 MB | 2,000 |
| Pro | 1 GB | 3,000 |
| Team | 2 GB | 3,000 |
| Enterprise | 50 GB | 50,000 |

Minute multipliers: Linux 1x, Windows 2x, macOS 10x.

### 27.3 Secrets Limits

- Org: 1,000 | Repo: 100 | Environment: 100
- Value size: 48 KB max
- Log retention: 90 days (400 for public repos)
- Artifact retention: 1-400 days (public), 1-90 days (free private)
- Cache: 10 GB per repo, 7-day eviction

---

## 28. Default Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_ACTION` | Current action/step ID |
| `GITHUB_ACTIONS` | Always `true` |
| `GITHUB_ACTOR` | Triggering user |
| `GITHUB_ACTOR_ID` | Actor account ID |
| `GITHUB_API_URL` | API URL |
| `GITHUB_BASE_REF` | PR base branch |
| `GITHUB_ENV` | Path to env file |
| `GITHUB_EVENT_NAME` | Event name |
| `GITHUB_EVENT_PATH` | Path to event payload JSON |
| `GITHUB_GRAPHQL_URL` | GraphQL URL |
| `GITHUB_HEAD_REF` | PR head branch |
| `GITHUB_JOB` | Job ID |
| `GITHUB_OUTPUT` | Path to output file |
| `GITHUB_PATH` | Path to PATH file |
| `GITHUB_REF` | Full ref |
| `GITHUB_REF_NAME` | Short ref name |
| `GITHUB_REF_PROTECTED` | Branch protection flag |
| `GITHUB_REF_TYPE` | `branch` or `tag` |
| `GITHUB_REPOSITORY` | `owner/repo` |
| `GITHUB_REPOSITORY_ID` | Numeric repo ID |
| `GITHUB_REPOSITORY_OWNER` | Owner name |
| `GITHUB_REPOSITORY_OWNER_ID` | Owner ID |
| `GITHUB_RETENTION_DAYS` | Artifact retention |
| `GITHUB_RUN_ATTEMPT` | Re-run attempt number |
| `GITHUB_RUN_ID` | Unique run ID |
| `GITHUB_RUN_NUMBER` | Sequential run number |
| `GITHUB_SERVER_URL` | Server URL |
| `GITHUB_SHA` | Commit SHA |
| `GITHUB_STEP_SUMMARY` | Path to summary file |
| `GITHUB_TOKEN` | Automatic token |
| `GITHUB_TRIGGERING_ACTOR` | Re-run triggering user |
| `GITHUB_WORKFLOW` | Workflow name |
| `GITHUB_WORKFLOW_REF` | Workflow file ref |
| `GITHUB_WORKFLOW_SHA` | Workflow file SHA |
| `GITHUB_WORKSPACE` | Working directory |
| `RUNNER_ARCH` | `X64`, `ARM64`, etc. |
| `RUNNER_DEBUG` | `1` if debug enabled |
| `RUNNER_ENVIRONMENT` | `github-hosted` or `self-hosted` |
| `RUNNER_NAME` | Runner name |
| `RUNNER_OS` | `Linux`, `Windows`, `macOS` |
| `RUNNER_TEMP` | Temp directory |
| `RUNNER_TOOL_CACHE` | Tool cache directory |

---

## 29. Open Source Implementations

### 29.1 nektos/act -- Local GitHub Actions Runner

**Repository**: https://github.com/nektos/act
**Language**: Go (~56k stars)

Complete reimplementation that runs workflows locally in Docker containers. NOT a port of the real runner.

**Architecture**:
- `pkg/runner/` -- job/step execution
- `pkg/model/` -- workflow YAML parser
- `pkg/exprparser/` -- expression language evaluator
- `pkg/container/` -- Docker container management
- `pkg/artifacts/` -- local artifact server

**Key design**: Docker-first (every job in a container), custom runner images (`catthehacker/ubuntu`), event simulation, action download/caching.

**Limitations**: No GITHUB_TOKEN (no backend), secrets from `.secrets` file, partial `github` context, no OIDC, no concurrency groups, partial reusable workflows.

### 29.2 Gitea Actions (Gitea + act_runner)

**Gitea** (https://gitea.io): Open-source Git service. Added Actions in v1.19 (2023).

**Architecture**:
- **Server-side** (built into Gitea): workflow parsing, event triggering, job scheduling, web UI, artifacts API
- **act_runner** (https://gitea.com/gitea/act_runner): Standalone Go binary built on `nektos/act` as a library

**Protocol**: gRPC-based (not GitHub's HTTPS long-poll)

```protobuf
// Key RPC methods
rpc Register(RegisterRequest) returns (RegisterResponse)
rpc FetchTask(FetchTaskRequest) returns (FetchTaskResponse)
rpc UpdateTask(UpdateTaskRequest) returns (UpdateTaskResponse)
rpc UpdateLog(UpdateLogRequest) returns (UpdateLogResponse)
```

**Compatibility**: Very high -- workflow syntax, expressions, `uses:` actions from GitHub, secrets/variables, GITHUB_TOKEN equivalent, container jobs, service containers.

### 29.3 Forgejo Actions

**Forgejo** (https://forgejo.org): Community fork of Gitea. Same Actions implementation, maintains own runner fork at https://code.forgejo.org/forgejo/runner.

### 29.4 Protocol Comparison

| Aspect | GitHub Runner | Gitea act_runner | nektos/act |
|--------|--------------|------------------|------------|
| Language | C# (.NET) | Go | Go |
| Communication | HTTPS long-poll / Broker | gRPC | N/A (local) |
| Authentication | RSA key pair + JWT | Registration token | N/A |
| Job dispatch | Server pushes via broker | Runner polls via FetchTask | Direct execution |
| Log streaming | HTTP upload in batches | gRPC UpdateLog | Stdout |
| Artifact storage | Azure Blob Storage | Gitea server | Local filesystem |
| Container execution | Docker CLI / hooks | Docker API (via act) | Docker API |

---

## 30. Implementation Guidance for Emulators

### 30.1 Server-Side Requirements

To emulate GitHub Actions, implement:

1. **Webhook event processing**: Match events against `.github/workflows/*.yml`
2. **Workflow YAML parser**: Parse GitHub Actions syntax including `${{ }}` expressions
3. **Job scheduler**: Build job DAG, handle matrix expansion, concurrency groups
4. **Runner registration API**: Registration tokens, runner CRUD, labels
5. **Job dispatch**: Queue jobs, dispatch to matching runners by labels
6. **Status tracking**: Workflow runs, jobs, steps with status/conclusion
7. **Log aggregation**: Receive and store log lines from runners
8. **Token provisioning**: Generate GITHUB_TOKEN equivalents per job
9. **API endpoints**: Artifacts, cache, secrets, variables REST APIs

### 30.2 Simplification Options

- **Use `nektos/act` as execution engine** (what Gitea did) instead of the C# runner
- **Use act as a Go library**: Import `pkg/runner`, `pkg/exprparser` directly
- **Simple HTTP REST** for runner communication (skip gRPC complexity)
- **Stub artifacts/cache**: Many workflows don't need them
- **Reuse act's expression evaluator**: Proven implementation

### 30.3 Recommended Approach (Gitea Model)

1. Server-side integrated into the Git hosting platform
2. Runner is a standalone binary using act's execution engine
3. Communication via clean protocol (REST or gRPC)
4. Very high GitHub Actions compatibility achieved

### 30.4 Runner Labels & Job Routing

When assigning jobs to runners:

1. Find all runners whose labels satisfy `runs-on` (AND logic -- all labels must match)
2. Filter by runner group access
3. Filter by runner status (online, idle, active session)
4. FIFO dispatch to first matching runner

Labels are case-insensitive. Default labels: `self-hosted`, OS (`Linux`/`Windows`/`macOS`), architecture (`X64`/`ARM`/`ARM64`).

---

## 31. Sources

### Official GitHub Documentation

- https://docs.github.com/en/rest/actions -- REST API reference
- https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions -- Workflow syntax
- https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows -- Events
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/evaluate-expressions-in-workflows-and-actions -- Expressions
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables -- Variables/contexts
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/using-jobs-in-a-workflow -- Jobs
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/using-a-matrix-for-your-jobs -- Matrix
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/using-conditions-to-control-job-execution -- Conditionals
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/caching-dependencies-to-speed-up-workflows -- Caching
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/using-concurrency -- Concurrency
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/assigning-permissions-to-jobs -- Permissions
- https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/workflow-commands-for-github-actions -- Workflow commands
- https://docs.github.com/en/actions/sharing-automations/creating-actions -- Custom actions
- https://docs.github.com/en/actions/sharing-automations/reusing-workflows -- Reusable workflows
- https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners -- Self-hosted runners
- https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners -- Adding runners
- https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/monitoring-and-troubleshooting-self-hosted-runners -- Runner monitoring
- https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/using-self-hosted-runners-in-a-workflow -- Using runners
- https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions -- Security
- https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions -- Secrets
- https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment -- Environments
- https://docs.github.com/en/actions/about-github-actions/usage-limits-billing-and-administration -- Limits
- https://docs.github.com/en/actions/publishing-packages -- Publishing
- https://docs.github.com/en/rest/actions/workflows -- Workflows API
- https://docs.github.com/en/rest/actions/workflow-runs -- Runs API
- https://docs.github.com/en/rest/actions/workflow-jobs -- Jobs API
- https://docs.github.com/en/rest/actions/artifacts -- Artifacts API
- https://docs.github.com/en/rest/actions/secrets -- Secrets API
- https://docs.github.com/en/rest/actions/variables -- Variables API
- https://docs.github.com/en/rest/actions/self-hosted-runners -- Runners API
- https://docs.github.com/en/rest/actions/self-hosted-runner-groups -- Runner groups API
- https://docs.github.com/en/rest/actions/permissions -- Permissions API
- https://docs.github.com/en/rest/actions/cache -- Cache API
- https://docs.github.com/en/rest/actions/oidc -- OIDC API

### Open Source Repositories

- https://github.com/actions/runner -- Official GitHub Actions runner (C#/.NET, MIT)
- https://github.com/actions/runner/tree/main/docs/design -- Runner design docs
- https://github.com/actions/runner/tree/main/docs/adrs -- Architecture decision records
- https://github.com/nektos/act -- Local Actions runner (Go)
- https://github.com/nektos/act/tree/master/pkg/runner -- act execution engine
- https://github.com/nektos/act/tree/master/pkg/exprparser -- act expression evaluator
- https://gitea.com/gitea/act_runner -- Gitea Actions runner
- https://github.com/go-gitea/gitea/tree/main/protos -- Gitea gRPC proto definitions
- https://docs.gitea.com/usage/actions/overview -- Gitea Actions docs
- https://code.forgejo.org/forgejo/runner -- Forgejo runner fork
- https://github.com/microsoft/azure-pipelines-agent -- Azure Pipelines agent (ancestor)

### Blog Posts & Talks

- GitHub Engineering blog: "How GitHub Actions Actually Works"
- Edward Thomson (ex-Azure DevOps PM): "Inside GitHub Actions"
- GitHub Universe conference talks on Actions architecture (2019-2023)
- Gitea blog: Actions design decisions (2023)
- GitHub Blog: "Actions self-hosted runners now support generation of JIT runner config" (2023-04-24)
