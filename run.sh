#!/usr/bin/env bash
# Wrapper for run.py that pins the uv-managed environment.
#
# All arguments are forwarded to run.py. Examples:
#   ./run.sh --ticker QQQ
#   ./run.sh --ticker QQQ --date 2026-04-29 --analysts all \
#            --provider claude_bridge --quick-model haiku --deep-model opus
#   ./run.sh --help
#
# Notes:
#   - `uv sync` keeps the .venv in lockstep with uv.lock; safe to re-run.
#   - We `cd` into the script's directory so relative paths (e.g. .env)
#     resolve correctly regardless of where the user invokes the wrapper.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: 'uv' not found on PATH. Install from https://docs.astral.sh/uv/" >&2
    exit 127
fi

# Keep deps in sync with the lock. Quiet so the wrapper stays unobtrusive.
uv sync --quiet

exec uv run python run.py "$@"
