#!/usr/bin/env bash
# Dispatch to a per-command pipeline script.
#
#   ./src/run.sh process  <obj ...> [--all] [--skip] [--workers N]
#   ./src/run.sh decimate <obj ...> [--all] [--target-faces N]
#   ./src/run.sh symmetry <obj ...> [--all]
#   ./src/run.sh tabletop <obj ...> [--all]
#
# (Each is also runnable directly, e.g. `python src/process.py --all`.)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cmd="${1:-}"
shift || true

case "$cmd" in
  process|decimate|symmetry|tabletop)
    exec python "$here/$cmd.py" "$@"
    ;;
  *)
    echo "usage: $0 <process|decimate|symmetry|tabletop> [args...]" >&2
    exit 2
    ;;
esac
