#!/usr/bin/env bash
{marker}
# Written by `roadmap install-cli`. Runs the CLI of the installed roadmap plugin, so it follows
# plugin updates; falls back to the copy install-cli ran from.
p="$(python3 - 2>/dev/null <<'PY'
import json, os
try:
    d = json.load(open(os.path.expanduser("~/.claude/plugins/installed_plugins.json")))
    for key, v in (d.get("plugins") or {}).items():
        if key.split("@")[0] == "roadmap" and v:
            print(v[0]["installPath"])
            break
except Exception:
    pass
PY
)"
[ -n "$p" ] && [ -f "$p/bin/roadmap" ] || p='{fallback}'
exec python3 "$p/bin/roadmap" "$@"
