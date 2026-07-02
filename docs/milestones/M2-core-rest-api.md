# M2: Core REST API

## Status

Complete

## Scope

Issues, pull requests, labels, milestones, and comments.

## Completed Work

- [x] Models: `Issue`, `Label`, `Milestone`, `IssueComment`, `PullRequest`, `IssueLabel`, `IssueAssignee`
- [x] Issues CRUD: list, create, get, update
- [x] Labels CRUD and issue label management
- [x] Milestones CRUD
- [x] Issue comments: list, create, get, update, delete
- [x] Pull requests: list, create, get, update, merge, list commits, list files
- [x] PR reviews: list, create, get, submit, dismiss
- [x] PR review comments: list, create, get, update, delete, list per review
- [x] Issue/PR numbering with shared auto-increment per repo via `next_issue_number`
- [x] PR merge logic with real git merge, squash, and rebase through a temporary clone
