# Bug: Pull request web page has no changed-files diff view

## Summary

The pull request detail page in the web UI did not provide a "Files changed"
view. Users could not inspect the diff for a PR from the browser.

## Status

Fixed.

## Reproduction

1. Open a repository pull request in the web UI, for example:
   `http://github.local/ui/opendatahub-io/odh-cli/pulls/3`
2. Inspect the PR page navigation and content.
3. Try to find a changed-files tab or rendered diff.

## Expected

The PR page should expose tabs similar to GitHub's PR UI:

- Conversation
- Commits
- Files changed

The "Files changed" view should list changed files and render patches for the
PR's base/head comparison.

## Actual

The page only rendered the conversation-style body and comments. There was no
changed-files tab and no diff output.

## Resolution

- Added `app.git.bare_repo.get_compare_diff()` to compute patch output for a
  PR base/head comparison using `git diff base...head`, with a `base..head`
  fallback.
- Updated `GET /api/v3/repos/{owner}/{repo}/pulls/{number}/files` to return
  changed files with filename, status, additions, deletions, changes, and patch
  fields instead of always returning `[]`.
- Added Conversation / Commits / Files changed tabs to the PR web detail page.
- Added a Files changed web view that renders per-file patch boxes using the
  existing commit diff presentation style.

## Verification

Ran:

```bash
uv run pytest tests/test_pulls_api.py -v
```

Result: 17 passed, 1 warning.

## Notes

- The PR web page still needs a merge button, tracked separately in
  `docs/bugs/open/pr-web-ui-missing-merge-button.md`.
- PR body markdown rendering is also tracked separately in
  `docs/bugs/open/pr-web-ui-renders-markdown-as-plain-text.md`.
