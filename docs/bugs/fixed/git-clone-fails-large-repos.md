# Bug: git clone fails for large repositories via Smart HTTP

## Summary

Cloning large repositories from the GitHub emulator via `git clone` fails with "remote end hung up unexpectedly." Small repositories clone successfully using the same credentials and method. This is the clone-side counterpart to the previously fixed push bug (`git-push-fails-large-repos.md`).

## Status

Fixed. The HTTP `git-upload-pack` endpoint no longer reads the request body
into memory with `request.body()` and no longer depends on a response iterator
consuming the ASGI request stream after the endpoint returns. It now spools the
fetch/clone request to a temporary file, feeds that file to `git-upload-pack`,
streams stdout back as `application/x-git-upload-pack-result`, drains stderr,
and removes the temporary file after the response stream finishes. The shared
spooling path also decodes gzip-encoded Git Smart HTTP request bodies before
passing them to Git.

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

1. **Confirmed: upload-pack request buffering and fragile stream timing**. The
   handler read the whole request body before invoking `git-upload-pack`. A
   direct request-streaming attempt avoided memory buffering but exposed an ASGI
   middleware deadlock risk when consuming `request.stream()` from the response
   iterator. The fixed path spools the request before returning the
   `StreamingResponse`.
2. **Mitigated: large pack response pressure**. The response remains streamed in
   64 KiB chunks from `git-upload-pack` stdout instead of being accumulated in
   memory.
3. **Possible external factor: proxy timeout**. Reverse proxies can still time
   out if Git itself takes too long before emitting response bytes, but the
   emulator no longer adds full request buffering or response accumulation to
   that path.
4. **Confirmed after live trace: gzipped upload-pack requests**. `git clone`
   against `github.local` sent `Content-Encoding: gzip` on
   `POST /git-upload-pack`. The emulator previously passed those compressed
   bytes directly to Git, which caused the server side to close a nominally
   successful HTTP 200 response without a valid pack stream.

## Notes

- The push path (`git-receive-pack`) was fixed in `git-push-fails-large-repos.md` by spooling the request to disk and running post-push work async. A similar streaming approach for `git-upload-pack` responses would likely fix this.
- Discovered during eval job `eval-arch-context-accuracy-opus-0703-143610` on 2026-07-03.
- Fixed by applying the same disk-spooling principle to upload-pack request
  input while preserving streamed stdout for the pack response.
- Fixed gzip handling by decoding compressed Smart HTTP request bodies in the
  shared spooling helper before upload-pack or receive-pack receives stdin.

## Verification

- `uv run pytest tests/test_git_http.py tests/test_git_integration.py -v`
  passed: 20 tests.
- Added regression coverage:
  `test_upload_pack_spools_request_and_streams_response` asserts upload-pack
  uses a spooled request body, streams the git response, and removes the temp
  file after the response completes.
- Added `test_spool_request_body_decodes_gzip` to cover Git clients that gzip
  Smart HTTP request bodies.
- Live deployed recheck after rebuild on 2026-07-06:
  `git -c http.sslVerify=false clone https://github.local/opendatahub-io/agent-eval-harness.git /tmp/agent-eval-harness-clone-recheck-20260706-1`
  completed successfully. The clone was on branch `main` at
  `b4299b8f0609479a96074537809c6841ebbec4a0`, and expected files such as
  `README.md`, `pyproject.toml`, `agent_eval/`, `tests/`, and `.github/` were
  present.

## Environment

- GitHub emulator running in K8s (ai-pipeline namespace)
- Accessed via Caddy reverse proxy at `github.local`
- Git client: system git
