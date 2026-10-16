#!/usr/bin/env bash
# Lint, test and build the package inside a clean Python container (nothing installed on the Mac).
set -euo pipefail
# Docker Desktop on macOS keeps the docker CLI inside the app: add it if it's not on PATH
command -v docker >/dev/null || export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c '
  pip install -q --root-user-action=ignore -e ".[dev]" &&
  echo "== lint ==" && ruff check src tests &&
  echo "== tests ==" && pytest -q &&
  echo "== build ==" && python -m build --wheel --outdir dist . >/dev/null &&
  ls dist && releasehub bump 1.4.2 minor'
# Same checks the way CI will run them: the Docker "test" stage
docker build --target test -q -t releasehub:test . >/dev/null && echo "== docker test stage: OK =="
