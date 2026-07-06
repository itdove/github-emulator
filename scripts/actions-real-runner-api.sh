#!/usr/bin/env bash
set -euo pipefail

export GITHUB_EMULATOR_DATA_DIR="${GITHUB_EMULATOR_DATA_DIR:-/tmp/ghemu-actions-real-runner}"
export GITHUB_EMULATOR_DATABASE_URL="${GITHUB_EMULATOR_DATABASE_URL:-sqlite+aiosqlite:////tmp/ghemu-actions-real-runner/github_emulator.db}"
export GITHUB_EMULATOR_BASE_URL="${GITHUB_EMULATOR_BASE_URL:-http://ghemu.local:8000}"
export GITHUB_EMULATOR_SSH_ENABLED="${GITHUB_EMULATOR_SSH_ENABLED:-false}"

uv run uvicorn app.main:app --host "${GITHUB_EMULATOR_HOST:-0.0.0.0}" --port "${GITHUB_EMULATOR_PORT:-8000}"
