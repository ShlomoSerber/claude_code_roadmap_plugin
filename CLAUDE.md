# claude_code_roadmap_plugin — harness notes

Start here: `README.md` (what it does, usage), `DESIGN.md` (why each choice, with what was checked), then the component the task touches. Update `DESIGN.md` when a design decision changes and `README.md` when behaviour changes.

## Facts a new session needs

| Thing | Where / value |
|---|---|
| Purpose | Plan a batch of tasks as a roadmap of session-sized units (`/roadmap:plan`), run it as fresh interactive sessions, in parallel where the dependency graph allows (`roadmap execute`), leave it unattended (`/roadmap:unattend`), answer what got blocked (`/roadmap:attend`). Origin: Farmagram `running-a-plan` and financial_tracker `running-the-roadmap` skills. |
| CLI | `bin/roadmap`, one Python 3 file, stdlib only. Everything that reads or writes `roadmap.json`, the runner (orchestrator), `worker` (one session), `slot` (a fixed Warp tab), worktree slots and merges, and the three hook handlers. User-facing text in Spanish (es-AR, voseo); text the model reads from hooks in English. |
| Skills | `skills/{plan,execute,session,attend,unattend}/SKILL.md`, all `disable-model-invocation: true`. `session` is what the runner launches (`/roadmap:session <name> <unit>`); its `!` preprocessing runs `roadmap brief`. Skills call the CLI as `"${CLAUDE_PLUGIN_ROOT}/bin/roadmap"` in `!` lines and as `roadmap` in instructions (the plugin's `bin/` is on the Bash tool PATH). |
| Hooks | `hooks/hooks.json` → `scripts/hook.sh <event>` → `bin/roadmap hook <event>`. `hook.sh` exits at once unless `ROADMAP_RUNNER=1`. PreToolUse (`AskUserQuestion|EnterPlanMode|ExitPlanMode`): deny when unattended. PostToolUse: heartbeat + context warnings at 60/80/93% of `context_limit`. Stop: signal present (or the unit already closed in `roadmap.json`) → SIGTERM the worker's child `claude` after 2 s; unattended without signal → block the stop, 4th time block the unit. Always exit 0, no network. |
| Roadmap files | `<repo>/.claude/roadmaps/<name>/`: `roadmap.json`, `ROADMAP.md`, `units/*.md`, `run/` (lock, runner.lock, runner.log, terminal.log, context-*.json, stop-blocks-*, `units/<id>/` launch.json, worker.pid, claude.pid, signal, heartbeat, last-session.json, exit.json, `slots/<n>/` host.pid, assign, quit). Excluded via `.git/info/exclude`. |
| Parallel | `parallel` > 1: worktree slots in `~/.local/share/claude-roadmap/worktrees/<repo>-<hash>/slot-<n>`, branch `roadmap/<name>/<unit>`, merged by the runner into `branch` (merge-tree test, then merge or commit-tree). Slots are trusted by writing `~/.claude.json`. In Warp: fixed slot tabs via Tab Configs (`~/.local/share/warp-terminal/tab_configs/roadmap-*.toml`, `xdg-open warp://tab_config/<name>`), focus handed back with xdotool. DESIGN.md §10. |
| Templates | `templates/`: `ROADMAP.md`, `unit.md`, `split-child.md` (Spanish headings: the briefs are for the user too), `shim.sh` (the `~/.local/bin/roadmap` shim that `install-cli` writes). |
| Usage | `/api/oauth/usage`, cached in `~/.cache/claude-roadmap/usage.json` (fresh 60 s, fallback 20 min), then the handoff status line cache. The endpoint rate-limits (429). |
| Install | Local directory marketplace `roadmap` → plugin `roadmap@roadmap`, user scope. Claude Code copies the plugin to `~/.claude/plugins/cache/roadmap/roadmap/<version>/`. Repo edits apply only after bumping `version` in `.claude-plugin/plugin.json`, then `claude plugin marketplace update roadmap && claude plugin update roadmap@roadmap`. The terminal shim follows the installed version. |
| Sibling plugins | `../claude_code_handoff_plugin` (same restart-by-new-process idea, status line with the same context measure), `../claude_code_archive_plugin`, `../claude_code_clear_language_plugin`. Same layout. |
| Testing | `python3 tests/test_split_task.py` (split units and the documentador task). Parallel e2e: same recipe with `TERM_PROGRAM=WarpTerminal` in the runner's env and `parallel: 2`; tabs open in the real Warp. Put `<repo>/bin` first on PATH and add `"roadmap@roadmap":false` to `enabledPlugins`, or sessions run the installed CLI through the `~/.local/bin/roadmap` shim. The repo under test must be trusted in `~/.claude.json` (slots inherit it). CLI and hooks: a throwaway git repo in the scratchpad, `roadmap init`, fake transcripts (`{"type":"assistant","message":{"usage":{…}}}` lines) piped to `scripts/hook.sh` with `ROADMAP_RUNNER=1 ROADMAP_DIR=… ROADMAP_UNIT=… ROADMAP_RUNNER_PID=<not an ancestor>`. End-to-end: drive `bin/roadmap execute <name> -- --plugin-dir <repo> --settings '{"enabledPlugins":{"archive@claude-code-archive":false,"handoff@handoff":false}}'` in a pty (python `pty.fork`), units on `haiku`, env without `CLAUDE*`/`ROADMAP_*`. A new folder shows the trust dialog with "No, exit" focused: send Down (`\x1b[B`), wait, then Enter as `\x1b[13u` (Claude Code enables the kitty keyboard protocol; a plain `\r` answers "No"). Trust does not inherit from a trusted parent folder. Never `pkill -f <pattern>` from the Bash tool: the pattern matches the tool's own shell. |

## Invariants

1. **Normal sessions pay nothing.** Every hook exits before Python unless `ROADMAP_RUNNER=1`.
2. **Only the CLI writes `roadmap.json`** after planning, under the `flock`, atomically, validated.
3. **The runner picks the unit**, deterministically; sessions never choose. With worktrees, only the runner merges and pushes.
4. **Unattended means no waiting.** Nothing in a runner session may wait for a person when `mode` is `unattended`: questions and plan mode are denied, stopping with the unit open is refused, idle sessions are closed.
5. **Documentador only on explicit request** in the planning conversation. Never by default, never offered.
6. **Nothing project-specific in the plugin.** Repo rules go in each roadmap's `ROADMAP.md`.

## Conventions

Python stdlib only; bash for `hook.sh`. Docs in English, terse. The user writes in Spanish (es-AR, voseo) and prefers autonomy: do the work, ask only before destructive or outward-facing actions. Commit and push only when asked.
