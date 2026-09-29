#!/usr/bin/env bash
# Entry point of every hook of the plugin (hooks/hooks.json). Outside a session launched by
# `roadmap execute` (ROADMAP_RUNNER=1) it exits at once, so normal sessions pay nothing.
# Inside one, bin/roadmap handles the event and always exits 0.
set -uo pipefail
[ "${ROADMAP_RUNNER:-}" = "1" ] || exit 0
exec python3 "$(dirname "${BASH_SOURCE[0]}")/../bin/roadmap" hook "$1"
