#!/usr/bin/env bash
set -euo pipefail

export GITHUB_EMULATOR_DATA_DIR="${GITHUB_EMULATOR_DATA_DIR:-/tmp/ghemu-large-push}"
export GITHUB_EMULATOR_DATABASE_URL="${GITHUB_EMULATOR_DATABASE_URL:-sqlite+aiosqlite:////tmp/ghemu-large-push/github_emulator.db}"
export GITHUB_EMULATOR_BASE_URL="${GITHUB_EMULATOR_BASE_URL:-http://127.0.0.1:8010}"
export GITHUB_EMULATOR_SSH_ENABLED="${GITHUB_EMULATOR_SSH_ENABLED:-false}"

mkdir -p "${GITHUB_EMULATOR_DATA_DIR}"
uv run uvicorn app.main:app --host 127.0.0.1 --port "${GITHUB_EMULATOR_PORT:-8010}"
