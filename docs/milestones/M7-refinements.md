# M7: Refinements

## Status

Complete

## Completed Work

- [x] OAuth web flow stubs at `/login/oauth/authorize` and `/login/oauth/access_token`
- [x] Rate limiting with in-memory counters per token/IP and `X-RateLimit-*` headers
- [x] `node_id` generation as base64-encoded `Type:id`
- [x] ETag middleware that computes SHA-1 of response body and honors `If-None-Match` with 304
- [x] Git SSH transport with asyncssh, public key auth via `SSHKey`, and git upload/receive pack support
