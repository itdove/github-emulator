# M3: Additional REST API

## Status

Complete

## Completed Work

- [x] Branches: list, get, get protection
- [x] Contents API: get, create, update, delete file contents via git commands; `auto_init` support
- [x] Git Data API: refs, commits, trees, blobs, tags
- [x] Commit statuses: create, get, combined status
- [x] Search: repos, issues, users, code, commits
- [x] Collaborators: list, check, add, remove, get permissions
- [x] Organizations: CRUD and members
- [x] Teams: CRUD, members, repos
- [x] Events API: public, repo, user events
- [x] Webhooks: CRUD and delivery listing
- [x] Forks: create fork, list forks
- [x] Starring: star, unstar, list stargazers
- [x] Releases and assets
- [x] Commits listing and compare
- [x] Check runs and suites
- [x] Deploy keys
- [x] Notifications
- [x] Reactions
- [x] Gists
- [x] SSH keys: DB-backed `SSHKey` model, full CRUD, public listing
- [x] GPG keys: DB-backed `GPGKey` model, full CRUD
- [x] Pagination with `page`, `per_page`, and `Link` headers
- [x] Webhook delivery with HMAC signing and delivery records
- [x] Search indexing with `FileContent` and `CommitMetadata` models; automatic indexing on push

## Runtime Verification

68 endpoints were tested against a running container and passed.

## Bugs Fixed During Verification

- Contents API returned 500 in container due to missing git identity environment variables.
- Contents API `PUT` returned 200 instead of 201 for new files.
- `POST /orgs` returned 404 because the endpoint was missing.
- `POST` reviews returned 200 instead of 201.
