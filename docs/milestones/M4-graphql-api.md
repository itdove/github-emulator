# M4: GraphQL API

## Status

Complete

## Completed Work

- [x] Strawberry GraphQL mounted at `/graphql` with `context_getter`
- [x] Core types: `Repository`, `Issue`, `PullRequest`, `User`
- [x] Relay connections with generic `Connection[T]` and cursor-based pagination
- [x] Root queries: `repository`, `user`, `viewer`, `organization`, `node`, `search`
- [x] Mutations: `createIssue`, `updateIssue`, `closeIssue`, `reopenIssue`, `addComment`, `createPullRequest`, `mergePullRequest`, `addReaction`, `createRepository`
- [x] 9 tests covering queries, mutations, variables, and auth
