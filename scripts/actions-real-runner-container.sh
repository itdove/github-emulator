#!/usr/bin/env bash
set -euo pipefail

IMAGE="${ACTIONS_REAL_RUNNER_IMAGE:-localhost/ghemu-actions-real-runner-test:latest}"
ENV_FILE="${ACTIONS_REAL_RUNNER_ENV_FILE:-.env}"
# Keep the test runner container name stable so follow-up docker exec/log
# commands can use a reusable approval rule.
CONTAINER_NAME="${ACTIONS_REAL_RUNNER_CONTAINER_NAME:-ghemu-actions-real-runner-test}"

if [[ "${1:-run}" == "stop" ]]; then
  docker stop "${CONTAINER_NAME}"
  exit 0
fi

docker run --rm \
  --name "${CONTAINER_NAME}" \
  --user root \
  --add-host ghemu.local:127.0.0.1 \
  --env-file "${ENV_FILE}" \
  -e RUNNER_ALLOW_RUNASROOT=1 \
  -e GITHUB_EMULATOR_URL="${GITHUB_EMULATOR_URL:-http://ghemu.local}" \
  -e GITHUB_EMULATOR_API_URL="${GITHUB_EMULATOR_API_URL:-http://host.containers.internal:8000/api/v3}" \
  -e GITHUB_EMULATOR_PORT80_PROXY_TARGET="${GITHUB_EMULATOR_PORT80_PROXY_TARGET:-http://host.containers.internal:8000}" \
  "${IMAGE}"
