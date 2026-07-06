# Bug: git clone fails for large repositories via Smart HTTP

## Summary

Cloning large repositories from the GitHub emulator via `git clone` fails with "remote end hung up unexpectedly." Small repositories clone successfully using the same credentials and method. This is the clone-side counterpart to the previously fixed push bug (`git-push-fails-large-repos.md`).

## Status

Open.

## Steps to Reproduce

1. Import a large upstream repo (e.g. agent-eval-harness) into the emulator using the admin import API:
   ```bash
   curl -X POST http://github.local/api/v3/admin/repos/import \
     -H "Authorization: token ghp_<ADMIN_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"clone_url": "https://github.com/opendatahub-io/agent-eval-harness.git", "owner": "opendatahub-io", "name": "agent-eval-harness"}'
   ```

2. Attempt to clone:
   ```bash
   git clone http://github.local/opendatahub-io/agent-eval-harness.git /tmp/agent-eval-harness
   ```

3. Observe: clone fails with "the remote end hung up unexpectedly" during pack negotiation or transfer.

## Affected Repos

- `opendatahub-io/agent-eval-harness` — clone fails from github.local

## Working Repos

- `opendatahub-io/eval-datasets` — small repo, clone works fine
- `opendatahub-io/rfe-creator` — small repo, clone works fine

## Workaround

Clone from upstream GitHub instead of github.local:
```bash
git clone https://github.com/opendatahub-io/agent-eval-harness.git /tmp/agent-eval-harness
```

Then push changes back to github.local (push works for incremental deltas):
```bash
cd /tmp/agent-eval-harness
git -c http.extraHeader="Authorization: token ghp_<ADMIN_TOKEN>" \
  push http://github.local/opendatahub-io/agent-eval-harness.git main
```

## Suspected Causes

1. **Upload-pack response buffering** — The Smart HTTP `git-upload-pack` handler likely buffers the full pack response in memory before sending, causing timeouts or OOM for large repos. The push path had an analogous issue (fixed by spooling to a temp file and async post-processing).
2. **Proxy timeout** — Caddy reverse proxy may time out waiting for the emulator to generate the full pack for large repos.

## Notes

- The push path (`git-receive-pack`) was fixed in `git-push-fails-large-repos.md` by spooling the request to disk and running post-push work async. A similar streaming approach for `git-upload-pack` responses would likely fix this.
- Discovered during eval job `eval-arch-context-accuracy-opus-0703-143610` on 2026-07-03.

## Environment

- GitHub emulator running in K8s (ai-pipeline namespace)
- Accessed via Caddy reverse proxy at `github.local`
- Git client: system git
