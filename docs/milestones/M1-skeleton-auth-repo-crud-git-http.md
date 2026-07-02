# M1: Skeleton, Auth, Repo CRUD, and Git Smart HTTP

## Status

Complete

## Completed Work

- [x] Project skeleton (`pyproject.toml`, `main.py`, `config.py`, `database.py`)
- [x] Core database models (`User`, `PersonalAccessToken`, `Repository`)
- [x] Authentication middleware with token, Bearer, Basic auth, and SHA-256 hashing
- [x] User and token API (`GET/PATCH /user`, `GET /users/{username}`, admin bootstrap endpoints)
- [x] Repository API with full CRUD and listing
- [x] Repository JSON response with 30+ URL template fields and permissions object
- [x] Git Smart HTTP (`info/refs`, `upload-pack`, `receive-pack`) with and without `.git` suffix
- [x] GitHub-compatible error responses for 401, 403, 404, and 422
- [x] Response headers (`X-RateLimit-*`, `X-GitHub-Media-Type`, `X-GitHub-Api-Version`)
- [x] Container setup (`Dockerfile`, `supervisord`, `docker-compose`)
- [x] Verification: clone, push, and pull working in container; pytest passing

## Bugs Fixed

- `WWW-Authenticate` header was stripped by error handler middleware, breaking git push auth.
- `pyproject.toml` had an invalid build backend.
- PR endpoints had `MissingGreenlet` errors from lazy-loading in async context.
- GraphQL `from __future__ import annotations` was incompatible with Strawberry type resolution.
- Admin user password was hashed with SHA-256 instead of bcrypt, causing passlib `UnknownHashError` on login.
- passlib and `bcrypt>=4.1` incompatibility caused startup `ValueError`; fixed by pinning `bcrypt<4.1`.
- Jinja2 `TemplateResponse` API change in Starlette 1.0 required `request` as a keyword arg.
