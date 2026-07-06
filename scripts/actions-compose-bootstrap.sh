#!/usr/bin/env bash
set -euo pipefail

API_BASE="${GITHUB_EMULATOR_API_URL:-http://localhost:8000/api/v3}"
RUNNER_REPO_VALUE="${RUNNER_REPO:-admin/test-repo}"
OWNER="${RUNNER_REPO_VALUE%%/*}"
REPO="${RUNNER_REPO_VALUE#*/}"

if [[ -z "$OWNER" || -z "$REPO" || "$OWNER" == "$RUNNER_REPO_VALUE" ]]; then
  echo "RUNNER_REPO must be owner/repo, got: $RUNNER_REPO_VALUE" >&2
  exit 2
fi

echo "Creating runner admin token through $API_BASE ..."
TOKEN="$(
  curl -sk -X POST "$API_BASE/admin/tokens" \
    -H "Content-Type: application/json" \
    -d '{"login":"admin","name":"compose-actions-runner","scopes":["repo","user","workflow"]}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
)"

echo "Ensuring repository $RUNNER_REPO_VALUE exists ..."
create_status="$(
  curl -sk -o /tmp/ghemu-actions-repo.json -w "%{http_code}" \
    -X POST "$API_BASE/user/repos" \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$REPO\",\"auto_init\":true}"
)"
if [[ "$create_status" != "201" && "$create_status" != "422" ]]; then
  cat /tmp/ghemu-actions-repo.json >&2 || true
  echo "Failed to create or confirm repository $RUNNER_REPO_VALUE (HTTP $create_status)" >&2
  exit 1
fi

cat > .env <<EOF
GITHUB_EMULATOR_RUNNER_TOKEN=$TOKEN
RUNNER_REPO=$RUNNER_REPO_VALUE
EOF

echo "Wrote .env for docker compose:"
echo "  GITHUB_EMULATOR_RUNNER_TOKEN=<redacted>"
echo "  RUNNER_REPO=$RUNNER_REPO_VALUE"
echo
echo "Next:"
echo "  docker compose up -d actions-runner"
echo "  make actions-ui-smoke"
