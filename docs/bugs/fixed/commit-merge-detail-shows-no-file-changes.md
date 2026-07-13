# Bug: Merge commit detail shows no file changes

## Status

Fixed.

## Summary

The web commit detail page can show `No file changes in this commit.` for a
merge commit that should expose a diff against its first parent.

## Reproduction

1. Open `/ui/opendatahub-io/odh-cli/commit/b675c400028837e9be8644c2f06331a279accbcf`.
2. Observe the commit header and parent list.
3. Scroll to the diff section.

## Expected

The merge commit page should show changed files and patches for the merge,
using GitHub-compatible behavior. For a normal merge commit, this should at
least show the diff relative to the first parent.

## Actual

The page renders the merge commit metadata, but the diff section says:

```text
No file changes in this commit.
```

Observed live data:

- Commit: `b675c400028837e9be8644c2f06331a279accbcf`
- Title: `Merge pull request #2 Merge epic/RHAI-4 into main`
- Parents: `1b6492023a80d5f9b523239a6492e345d56c6687` and
  `91f7f58d4c93c21217ad448c60dd7ba45ad036a0`

## Impact

Reviewing merge commits from the web UI loses the most important part of the
commit detail page: what changed. This also makes successful PR merges look
empty even when they advanced the base branch.

## Notes

This is distinct from the PR Files changed tab. The problem was observed on the
single commit detail view after navigating directly to a merge commit.

## Fix

Updated `get_commit_diff` so commit detail diffs are generated against the
commit's first parent. Root commits use the empty-tree diff fallback.

Added regression coverage to the web merge flow so a generated merge commit
detail page must render the changed file, patch content, and must not show the
empty diff message.

## Verification

```bash
uv run pytest tests/test_pulls_api.py::test_pr_web_merge_button_merges_pull_request -v
uv run pytest tests/test_pulls_api.py -v
git diff --check
```

Result:

- Focused merge commit detail regression passed.
- Full pull request API/web test file passed: 20 passed, 1 warning.
- Diff whitespace check clean.
