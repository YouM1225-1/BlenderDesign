#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONDONTWRITEBYTECODE=1
./.venv/bin/ruff check --no-cache .
./.venv/bin/mypy --cache-dir=/dev/null
./.venv/bin/python -m pytest -p no:cacheprovider --ignore=tests/distribution -q
