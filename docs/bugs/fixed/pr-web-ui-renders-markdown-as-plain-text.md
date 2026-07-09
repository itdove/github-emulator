# Bug: Pull request web page renders Markdown as plain text

## Summary

Pull request bodies and comments were displayed as raw Markdown in the web UI
instead of rendered HTML.

## Status

Fixed.

## Reproduction

1. Open a pull request with Markdown in its body, for example:
   `http://github.local/ui/opendatahub-io/odh-cli/pulls/3`
2. Observe the PR body.

## Expected

Markdown should render into readable HTML:

- headings should render as headings
- bold text should render as bold text
- tables should render as tables
- task lists should render as checklist items
- inline code should render with code styling

## Actual

The raw source was shown directly, including `##`, `**bold**`, pipe-table
syntax, `- [ ]` task markers, and backticks.

## Resolution

- Added `app.web.markdown.render_markdown()` for a safe subset of Markdown used
  by PR conversation text.
- Rendered PR bodies and comments through that helper in the PR web detail
  route.
- Updated the PR detail template to output rendered HTML inside
  `markdown-body` containers.
- Added scoped web CSS for rendered headings, inline code, tables, and task
  lists.
- Added a regression test covering PR body and comment Markdown rendering,
  including escaped unsafe HTML.

## Verification

Ran:

```bash
uv run pytest tests/test_pulls_api.py -v
```

Result: 18 passed, 1 warning.

## Notes

- The renderer intentionally preserves raw Markdown storage and API response
  bodies; this fix only changes web presentation for PR conversation text.
- The PR web page still needs a merge button, tracked separately in
  `docs/bugs/open/pr-web-ui-missing-merge-button.md`.
