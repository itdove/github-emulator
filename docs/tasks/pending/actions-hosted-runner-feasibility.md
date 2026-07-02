# Task: Hosted Runner Feasibility

## Goal

Determine whether GitHub-owned hosted runners can execute jobs for this emulator,
and document the recommended runner strategy.

## Context

GitHub-hosted runners are managed by GitHub for GitHub Actions workflows. The
emulator has its own API, database, workflow scheduler, and partial runner
protocol endpoints. The project already contains a self-hosted-style Docker
runner service.

Official GitHub documentation says GitHub-hosted runners are GitHub-provided
machines for GitHub Actions workflows, while self-hosted runners are systems the
user deploys and manages. Current evidence points toward this emulator needing
self-hosted or emulator-hosted runners, ideally using the real `actions/runner`
binary for maximum compatibility, not GitHub-owned hosted runners.

## Research Questions

- [x] Can GitHub-hosted runners be registered against a non-GitHub service URL?
- [x] Can GitHub-hosted runners be used with GitHub Enterprise Server or only
      with GitHub.com / Enterprise Cloud workflow orchestration?
- [x] Is there any supported API for external schedulers to dispatch jobs onto
      GitHub-owned hosted runners?
- [x] Can larger runners/custom images help this emulator, or are they also
      bound to GitHub's hosted Actions control plane?
- [ ] Is the real `actions/runner` binary usable against the emulator's partial
      GHES/Azure Pipelines-compatible endpoints?
- [x] Would Actions Runner Controller or ephemeral self-hosted runners be a more
      realistic "hosted runner" story for this stack?

## Likely Outcome To Verify

GitHub-owned hosted runners are probably not directly usable because job
dispatch, lifecycle, billing, identity, and repository checkout are controlled
by GitHub's Actions service. The practical path is likely:

1. local Docker runner for development
2. real `actions/runner` compatibility for maximum fidelity
3. optional ephemeral self-hosted runners managed by this stack
4. optional Kubernetes/ARC-style runner scale sets if the emulator grows beyond
   Docker Compose

## Evidence Required

- [x] Links to official GitHub documentation for GitHub-hosted runners.
- [x] Links to official GitHub documentation for self-hosted runners.
- [x] If investigating GHES support, links to official GHES Actions runner docs.
- [x] A written conclusion in `docs/decisions/` if the project decides not to
      pursue GitHub-owned hosted runners.
- [ ] A spike result if testing real `actions/runner` against the emulator.

## Sources Checked So Far

- GitHub Docs: GitHub-hosted runners
  `https://docs.github.com/en/actions/concepts/runners/github-hosted-runners`
- GitHub Docs: Self-hosted runners
  `https://docs.github.com/en/actions/concepts/runners/self-hosted-runners`
- GitHub Enterprise Server Docs: Adding self-hosted runners
  `https://docs.github.com/en/enterprise-server@3.17/actions/how-tos/manage-runners/self-hosted-runners/add-runners`
- GitHub Docs: Larger runners
  `https://docs.github.com/en/actions/concepts/runners/larger-runners`
- GitHub Docs: Actions Runner Controller
  `https://docs.github.com/en/actions/concepts/runners/actions-runner-controller`
- GitHub Docs: Runner scale sets
  `https://docs.github.com/en/actions/concepts/runners/runner-scale-sets`

## Status

Pending

## Notes

- Do not spend implementation time chasing GitHub-owned hosted runners until the
  support boundary is confirmed from official sources.
- Current recommendation is recorded in
  `docs/decisions/ADR-0001-actions-runner-strategy.md`: use emulator-managed
  runners, with real `actions/runner` compatibility as the preferred target,
  rather than GitHub-owned hosted runners.
- GitHub Enterprise Server 3.17 documentation explicitly says GHES users should
  use self-hosted runners and that GitHub-hosted runners are not supported.
- Larger runners and custom images are still GitHub-hosted runner features for
  GitHub Team or GitHub Enterprise Cloud organizations and enterprises, so they
  do not provide an external execution backend for this emulator.
- ARC and runner scale sets are a plausible future scaling model only after the
  emulator can speak enough of the runner protocol, because ARC still uses
  self-hosted runners controlled through the GitHub Actions service model.
