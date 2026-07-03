#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${GITHUB_EMULATOR_BASE_URL:-http://127.0.0.1:8010}"
WORKDIR="${GITHUB_EMULATOR_LARGE_PUSH_WORKDIR:-/tmp/ghemu-large-push-repro}"
OWNER="${GITHUB_EMULATOR_LARGE_PUSH_OWNER:-largepush}"
REPO="${GITHUB_EMULATOR_LARGE_PUSH_REPO:-large-repo-$(date +%s)}"
REF_COUNT="${GITHUB_EMULATOR_LARGE_PUSH_REF_COUNT:-700}"
FILE_COUNT="${GITHUB_EMULATOR_LARGE_PUSH_FILE_COUNT:-200}"

rm -rf "${WORKDIR}"
mkdir -p "${WORKDIR}"

curl -fsS -X POST "${BASE_URL}/api/v3/admin/users" \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"${OWNER}\",\"email\":\"${OWNER}@example.com\",\"password\":\"password\"}" \
  >/dev/null || true

TOKEN="$(
  curl -fsS -X POST "${BASE_URL}/api/v3/admin/tokens" \
    -H "Content-Type: application/json" \
    -d "{\"login\":\"${OWNER}\",\"name\":\"large-push\",\"scopes\":[\"repo\",\"user\"]}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
)"

curl -fsS -X POST "${BASE_URL}/api/v3/user/repos" \
  -H "Authorization: token ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${REPO}\",\"auto_init\":true}" \
  >/dev/null

SOURCE="${WORKDIR}/source"
git init -b main "${SOURCE}" >/dev/null
git -C "${SOURCE}" config user.name "Large Push"
git -C "${SOURCE}" config user.email "largepush@example.com"

for index in $(seq 1 "${FILE_COUNT}"); do
  printf 'large push file %s\n' "${index}" > "${SOURCE}/file-${index}.txt"
done

git -C "${SOURCE}" add .
git -C "${SOURCE}" commit -m "large push seed" >/dev/null

for index in $(seq 1 "${REF_COUNT}"); do
  git -C "${SOURCE}" branch "synthetic/${index}"
done

REMOTE_URL="${BASE_URL/http:\/\//http://x-access-token:${TOKEN}@}/${OWNER}/${REPO}.git"
git -C "${SOURCE}" remote add emulator "${REMOTE_URL}"
git -C "${SOURCE}" push emulator --mirror
git ls-remote "${REMOTE_URL}" "refs/heads/synthetic/${REF_COUNT}" | grep "refs/heads/synthetic/${REF_COUNT}"

echo "large push succeeded: ${OWNER}/${REPO} (${REF_COUNT} refs, ${FILE_COUNT} files)"
