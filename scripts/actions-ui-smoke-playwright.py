#!/usr/bin/env python3
"""Desktop Playwright smoke validation for the Actions UI.

Run this against a live compose stack after seeding a repository with at least
one workflow run:

    python scripts/actions-ui-smoke-playwright.py \
      --base-url http://localhost:8000 \
      --repo testuser/web-actions-repo

The script intentionally depends on Playwright only when executed:

    python -m pip install playwright
    python -m playwright install chromium
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--repo", required=True, help="owner/repo")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright, expect
    except ImportError:
        print("Playwright is not installed. Install with: python -m pip install playwright", file=sys.stderr)
        return 2

    base = args.base_url.rstrip("/")
    owner_repo = args.repo.strip("/")
    actions_url = f"{base}/ui/{owner_repo}/actions"
    runners_url = f"{base}/ui/{owner_repo}/actions/runners"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(actions_url, wait_until="networkidle")
        expect(page.get_by_role("link", name="Actions")).to_be_visible()
        expect(page.get_by_text("Workflows")).to_be_visible()
        expect(page.get_by_text("Recent Runs")).to_be_visible()

        first_run = page.locator('a[href*="/actions/runs/"]').first
        if first_run.count() > 0:
            first_run.click()
            expect(page.get_by_text("Run metadata")).to_be_visible()
            first_job = page.locator('a[href*="/actions/jobs/"]').first
            if first_job.count() > 0:
                first_job.click()
                expect(page.get_by_text("Job metadata")).to_be_visible()
                expect(page.get_by_text("Steps")).to_be_visible()
                expect(page.get_by_text("Logs")).to_be_visible()

        page.goto(runners_url, wait_until="networkidle")
        expect(page.get_by_text("Repository runners")).to_be_visible()
        browser.close()

    print("Actions UI desktop smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
