# Bug: Pull request web page has no merge button

## Summary

The pull request detail page in the web UI did not expose a merge action. A
viewer could see the PR title, state, branch labels, body, and comments, but
there was no merge box or button for an open mergeable PR.

## Status

Fixed.

## Reproduction

1. Open a repository pull request in the web UI, for example:
   `http://github.local/ui/opendatahub-io/odh-cli/pulls/3`
2. Observe that the page renders the PR conversation.
3. Look below the conversation or near the PR state header for a merge control.

## Expected

Open pull requests should show a merge/status box with an actionable merge
button when the current user has permission and the PR is mergeable. The control
should call the existing merge behavior and refresh or redirect back to the PR
page showing the merged state.

## Actual

No merge button or merge status box was rendered.

## Resolution

- Added a PR merge/status box to the web PR conversation tab.
- Added permission-aware merge controls:
  - unauthenticated users see a sign-in prompt
  - users without write permission do not get a merge form
  - repository owners, collaborators with write-level permissions, and site
    admins can merge
- Added `POST /ui/{owner}/{repo}/pulls/{number}/merge` to merge from the web UI.
- The web route updates the PR/issue state, attempts the same git merge helper
  used by the REST API, and redirects back to the PR page in the merged state.
- Added a regression test proving the button appears for an authenticated owner,
  the POST route redirects, the web page shows the merged state, and the REST PR
  response reports the PR as merged and closed.

## Verification

Ran:

```bash
uv run pytest tests/test_pulls_api.py -v
```

Result: 19 passed, 1 warning.
