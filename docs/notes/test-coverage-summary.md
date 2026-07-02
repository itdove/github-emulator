# Test Coverage Summary

Last updated: 2026-04-08

| File | Tests | Covered Area |
|------|-------|--------------|
| `test_auth.py` | 7 | Token/Bearer/Basic auth, public user, 401 on invalid |
| `test_repos_api.py` | 9 | Repo CRUD, listing, auth required, duplicate, response format |
| `test_issues_api.py` | 6 | Issue CRUD, numbering, state filtering |
| `test_pulls_api.py` | 15 | PR CRUD, merge, draft, state filtering, shared numbering |
| `test_git_http.py` | 11 | `info/refs`, upload-pack, receive-pack, auth, cache headers |
| `test_labels_api.py` | 15 | Label CRUD, issue label management, duplicates |
| `test_comments_api.py` | 13 | Comment CRUD, auth, response shape |
| `test_search_api.py` | 11 | Search repos/issues/users, pagination, response shape |
| `test_branches_api.py` | 8 | Branch listing, retrieval, protection, 404s |
| `test_misc_api.py` | 21 | Emojis, gitignore, licenses, markdown, meta, root, rate_limit |
| `test_milestones_api.py` | 10 | Milestone CRUD, numbering, due dates, state filtering |
| `test_contents_api.py` | 11 | File get/create/update/delete, base64 encoding, README |
| `test_webhooks_api.py` | 8 | Webhook CRUD, config shape, URL validation |
| `test_collaborators_api.py` | 8 | Add/list/check/remove collaborator, permissions |
| `test_forks_api.py` | 6 | Create fork, list forks, custom name, duplicates |
| `test_orgs_api.py` | 10 | Org CRUD, members, user orgs, response format |
| `test_graphql.py` | 9 | Viewer, repository, user, search, issues, variables |
| `test_admin.py` | 8 | Login page, auth, users, repos, logout |
| `test_git_integration.py` | 6 | `info/refs`, upload-pack, auth, 404s |
| `test_etag.py` | 5 | ETag header, `If-None-Match` 304, consistency |
| `test_review_comments_api.py` | 9 | Review comment CRUD, validation, response format |
| `test_user_keys_api.py` | 13 | SSH/GPG key CRUD, public endpoint |
| **Total** | **219** | |
