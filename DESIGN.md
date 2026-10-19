# Design notes

Research date: 2026-09-29. Claude Code 2.1.284. Origin: the `running-a-plan` skill of the Farmagram repo and the `running-the-roadmap` skill of `financial_tracker`, both written on 2026-09-28. This plugin generalizes their runner and adds a schema, a model per unit, context awareness and an unattended mode.

## 1. Why not Claude Code's plan mode

Checked in the 2.1.284 binary. Plan mode (`/plan`, Shift+Tab, `EnterPlanMode`/`ExitPlanMode`) makes the session read-only, runs a four-phase prompt (explore, design, review, write), writes a markdown plan to `~/.claude/plans/` (or `plansDirectory`), and asks for approval. After approval the model only gets "User has approved your plan. You can now start coding." Execution happens in the same session, with the todo list as its only state. Nothing tracks steps across sessions, resumes a plan, or knows about context size or plan limits. `/ultraplan` drafts the plan in a cloud session; execution is the same.

Roadmap covers the part plan mode leaves out: a batch of tasks executed as many small sessions. The plugin is named `roadmap`, not `plan`, because `/plan` is a built-in command.

## 2. The schema

`roadmap.json`, one file per roadmap:

| Field | Meaning |
|---|---|
| `schema` | 1 |
| `name`, `title`, `created` | kebab-case name (the directory), human title, date |
| `mode` | `attended` or `unattended`. Read by the hooks on every call and by the runner before every session, so a change applies at once. |
| `permission_mode` | `bypass` (default, `--dangerously-skip-permissions`), `auto`, `acceptEdits`, `default` |
| `context_limit` | tokens per session; the post-tool hook warns at 60/80/93% of it. Default 150000. |
| `limits` | `five_hour` (wait for the reset), `weekly` (stop), `fable` (stop before a Fable unit). Percent of the plan limit. Defaults 95/70/90: the thresholds of the original runners, plus Fable. Optional `weekly_action`: `stop` (default) or `wait` for the weekly reset, as the 5-hour limit does. `roadmap config limits.<key>=…` changes them. |
| `default_model` | `opus` |
| `documentador` | `null`, or `{"project_id": …}` when the user asked for it |
| `parallel` | sessions at the same time, 1-8. `1` (and missing): one session at a time in the repo's own checkout. More: worktrees (§10). |
| `branch`, `push`, `setup` | parallel only: the branch closed units merge into (default: the repo's current branch, saved at the first run), whether the runner pushes it after each merge, and shell commands every worktree runs before its session |
| `units[]` | `id`, `title`, `file`, `model`, `est_tokens`, `depends_on`, `touches` (paths the unit edits), `status`, `task`; runtime: `started_at`, `finished_at`, `handoffs`, `sessions[]` (context at first and last reply, signal, transcript), `blocked` (`question`, `since`), `history[]`, `children`, `parent`, `merged_at`, `pending_merge` |

Statuses: `pending`, `in_progress`, `done`, `blocked`, `split`. A split unit's dependents wait for all its children. `depends_on: ["*"]` waits until every other unit is done, blocked, or stuck behind a blocked unit: the Farmagram "final" unit, generalized (plan 4 of Farmagram lost its final test run because the last unit blocked and nothing owned the run).

JSON, not a markdown table: the Farmagram runner counted states with a regex over `INDEX.md`, which breaks on a hand edit. Sessions change state only through the CLI (`done`, `handoff`, `block`, `split`, `set`), which validates and writes atomically under a `flock`. Briefs stay markdown, because people and models read them.

The runner picks the unit, not the session. It needs the unit before launching, to pass `--model`, and the choice is deterministic: first `in_progress`, else first `pending` whose dependencies are met, in file order. In parallel it takes as many as there are free slots, in the same order (§10).

## 3. The runner

`roadmap execute` is the loop from the original runners, in Python. This section describes one session at a time (`parallel: 1`); §10 adds the parallel case, which reuses every step:

1. Validate, pick the unit, check usage (below), mark it `in_progress`.
2. Write the launch spec (`run/units/<id>/launch.json`) and start `roadmap worker`, which launches interactive `claude --model <m> --dangerously-skip-permissions "/roadmap:session <name> <unit>"` with `ROADMAP_RUNNER=1`, `ROADMAP_DIR`, `ROADMAP_UNIT`, `ROADMAP_RUNNER_PID` (the worker's pid). Session variables of any enclosing Claude Code session (`CLAUDECODE`, `CLAUDE_PID`, …) are stripped. The worker records the pids and writes `exit.json` when `claude` ends, so the runner watches files, not a child process.
3. The session closes its unit with a CLI command, which writes `run/units/<id>/signal`. The Stop hook sees it when the turn ends and SIGTERMs the `claude` process: the worker's direct child, found by walking up from the hook. It waits 2 s first, so the last message is painted. If the signal is missing but `roadmap.json` already shows the unit closed (a CLI of another plugin version wrote it elsewhere; seen in testing), the hook writes the signal from the state and ends the session anyway.
4. The runner reads the signal: `next` (done or split), `continue` (handoff; three in a row stop the run when attended, block the unit when unattended), `blocked` (go on with the next eligible unit).

Why a new process: nothing can run `/clear` for the model (checked for the handoff plugin, DESIGN.md §6 there), and `claude -p` hides the session. The user wants to watch and to talk to a session.

Ctrl+C: while a session runs, the runner's SIGINT handler is a Python function, which `exec` resets to the default, so the session still handles Ctrl+C and the runner survives. `SIG_IGN` would be inherited and break Ctrl+C in the session. During the pause between sessions, Ctrl+C stops the runner. Quitting a session yourself stops it too, in attended mode: no signal means someone intervened.

A session that ends without a signal in under 45 s never reached its unit: the folder trust dialog answered "No" (its default), an unknown model, no login. The runner stops instead of retrying. Found in the first end-to-end test, where the unattended runner blocked three units in 20 seconds.

`/roadmap:execute` cannot host the runner, because the runner must outlive every session. It opens `roadmap execute` in a new Warp tab when the session runs in Warp, else a new `gnome-terminal`, with the session variables stripped. The same name works in the terminal: `roadmap execute`.

`--new-terminal` reports success only after the runner logs `runner start` in `run/runner.log` or holds `runner.lock`, within 30 s; else it fails with the runner's exit message or a pointer to `run/terminal.log` (the terminal's stderr). The wait matters beyond the message: a caller that ends at once inside its own cgroup (a systemd timer, `KillMode=control-group`) takes the `gnome-terminal` client down with it before it asks the server for the window. Bug of 2026-10-16: a timer relaunch printed "abierto" and nothing opened. The runner also logs `wait: <why>` (once per wait, then `wait over`), `stop: <why>` and `exit: <why>` (from `fail`/`die` once it owns the roadmap), so the reason survives the closed tab.

## 4. Usage limits

Before each session the runner reads `https://api.anthropic.com/api/oauth/usage` with the OAuth token of `~/.claude/.credentials.json`, the endpoint `/usage` uses. The `limits` array has `kind: session` (5 hours), `weekly_all`, and `weekly_scoped` with `scope.model.display_name: "Fable"`. Older fields `five_hour` and `seven_day` are the fallback. If usage cannot be read, the runner goes on, as the original runners did. The limits are absolute thresholds, the user's choice on 2026-09-29, not a budget relative to the roadmap's start. `limits.weekly_action: "wait"` (added 2026-10-16) makes the weekly limit wait like the 5-hour one, rechecking every 10 minutes, so an overnight reset needs no external relaunch. The Fable limit keeps skipping Fable units.

## 5. Context awareness

A `PostToolUse` hook reads `transcript_path` and takes the usage of the last main-thread assistant reply: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, the same measure the handoff status line uses. That is the context the next request carries. When it crosses 60%, 80% or 93% of `context_limit`, the hook returns `additionalContext` with the size and what to do: plan the close; decide between finish, hand off and split; stop new work. Past 93% it repeats every fifth tool call. It stays quiet otherwise, so it costs nothing until it matters.

The model decides, because only it knows how much of the unit is left. The CLI gives it the three exits: `handoff` (same unit, next session, from a Nota de traspaso), `split` (children `<id>.1…`, each depending on the previous, briefs it fills in; the documentador task stays with the split unit, §7), and `done`.

Measured context goes back into the roadmap: the Stop hook stores the first and last reply's context in `run/last-session.json`, and the runner saves it in the unit's `sessions`. `roadmap status` shows estimated vs real, so later plans size better. The first reply's context is the session's fixed cost. `roadmap baseline` estimates it before any run: 25k of system prompt and tools, plus the CLAUDE.md files the session loads (Farmagram's alone is ~30k).

## 6. Unattended mode

A prompt that says "do not ask" is not enough: the model asks anyway, and one question waits all night. Enforcement is in hooks:

- `PreToolUse` on `AskUserQuestion|EnterPlanMode|ExitPlanMode`: deny, with the reason telling the model to assume (minor) or block (real), and the exact command.
- `Stop` without a signal: `{"decision": "block"}` with the same instruction, up to three times per session. On the fourth, the hook blocks the unit itself ("the session kept stopping; see its transcript"), writes the signal, and ends the session.
- The runner: `blocked` never stops the run; a unit that hands off three times is blocked with a split question; a session with no hook activity (heartbeat file, touched on every tool call and stop) for 30 minutes is closed and retried; a session that ends without a signal is retried instead of stopping the run.

The Bash tool's own timeout (10 min max) bounds a single tool call, so 30 idle minutes means a stuck session, not a long test.

`/roadmap:unattend` runs `roadmap unattend` in its preprocessing, so the switch happens before the model reads the skill, and then tells a runner session to continue its unit under the new rules. `/roadmap:attend` switches back and walks the blocked questions. Block questions are written for that moment: self-contained, with options and a recommendation, because the person answering has none of the session's context.

## 7. Planning

`/roadmap:plan` exists to make the run need nobody: the interview checklist (scope, behavior, external needs, git policy, verification, forbidden actions) and a readiness test per unit ("could a fresh session with only ROADMAP.md and this file do it without asking?"). Decisions are copied into each brief in full, never pointed at, because no session sees the planning conversation.

The documentador is used only when the user explicitly asks for it in the planning conversation. It is never offered or done by default: the user's rule, 2026-09-29.

**Split units and their task.** A unit's task belongs to the whole unit, so a split does not copy it: `split` creates the children with `task: null`, and the brief resolves the task by walking up `parent`. For every task found (the unit's own, then each ancestor's), the brief says whether this session completes it or only comments. It completes when no other part of the task's unit is open: the leaves under that unit, through nested splits, that are not `done`, this unit excluded. A blocked part counts as open. The other parts comment (`add_task_comment`); the last one runs `complete_task` with an output covering the whole unit. Resolving at brief time, not at split time, handles nested splits, parts added later, and a part dropped in `/roadmap:attend` without any bookkeeping. `roadmap task` prints the same lines, recomputed when the session closes. Before this (v0.2.2), children got `Documentador: off` and the split unit's task stayed In Progress forever: six Farmagram tasks, closed by hand on 2026-10-19. `tests/test_split_task.py` covers it.

Session rules default to the lessons of the original skills: no subagents (each pays the fixed context again; a 30-hour Farmagram run with subagents exhausted the account), targeted reads, commit when green, never close red, findings go to the closing note. `ROADMAP.md` can override them.

## 8. Hooks

All hooks go through `scripts/hook.sh`, which exits at once unless `ROADMAP_RUNNER=1`. Normal sessions, and hand-opened sessions in a repo with a roadmap, are never touched. Inside a runner session the Python handler catches everything and always exits 0: a hook must never break a session. No network in hooks.

## 9. The CLI outside Claude

Claude Code puts a plugin's `bin/` on the Bash tool's PATH, not on the user's terminal PATH. `roadmap install-cli` writes `~/.local/bin/roadmap`, a shim that reads `~/.claude/plugins/installed_plugins.json` and runs the installed version's `bin/roadmap`, so it follows plugin updates. It falls back to the copy that installed it.

## 10. Parallel runs

Added 2026-10-07 (Claude Code 2.1.293, Warp 0.2026.09.30 on Ubuntu, GNOME on Wayland, git 2.48).

**What runs together.** The plan already has a dependency graph (`depends_on`); `/roadmap:plan` now draws it as waves, keeps only real dependencies, and adds `touches`, the paths a unit edits. The runner fills free slots with the first ready units in file order. Ready means: dependencies done *and merged*; a split child also waits for its parent's merge; and no running unit shares a `touches` path (prefix match at `/` boundaries). The `*` unit waits until nothing else runs. The user accepted the higher chance of hitting the plan limits: the usage check stays before each launch; the 5-hour limit pauses new launches, the weekly limit stops them, the Fable limit skips Fable units. Sessions already running finish.

**Git: worktree slots.** Parallel sessions in one checkout collide (one runs tests while another edits; `git add` takes another's files). Each session works in a git worktree, on the unit's branch `roadmap/<name>/<unit>`. The worktrees are **slots**, reused across units: `~/.local/share/claude-roadmap/worktrees/<repo>-<hash>/slot-<n>`, outside the repo, so a session does not load the repo's `CLAUDE.md` twice (Claude Code reads every `CLAUDE.md` from the cwd up). Reuse means the folder trust and installed dependencies (`setup`) are paid once per slot, not per unit. Between sessions a slot is left detached and clean; uncommitted leftovers go to `git stash` with a note in the unit brief, never deleted.

**Folder trust.** A slot is a new folder, so Claude Code would show the trust dialog, and nobody can answer it in an unattended run (trust does not inherit from a parent folder). The runner sets `projects[<slot>].hasTrustDialogAccepted` in `~/.claude.json`, only for slots of a repo the user already trusts, before every launch (Claude Code rewrites that file often). The write is an atomic replace; a concurrent rewrite by a running Claude Code can drop it, which the re-check before the next launch repairs.

**Integration.** The runner, not the sessions, merges. When a unit closes, its branch is test-merged with `git merge-tree --write-tree` (no side effects). Clean: if the repo's own checkout is on `branch`, a normal `git merge --no-ff` there (so that checkout stays in sync); otherwise `commit-tree` + `update-ref`, which touches no working tree. Then `merged_at` is set, the unit branch deleted, and `branch` pushed if `push`. A conflict goes back to a session, which has the unit's context: a done unit returns to `in_progress` with `pending_merge: <branch>`, and its next session merges `branch` into its own and resolves; a split parent hands `pending_merge: <parent branch>` to its first child. The brief prints the pending merge as the first thing to do. A merge that fails for another reason (the repo checkout dirty on the same files) is retried every minute. Tested end to end: two haiku units creating the same file in parallel; the second merge conflicted, a new session merged and kept both lines, the runner integrated it.

**Per-unit run files.** Everything a session and its hooks share with the runner moved from `run/` to `run/units/<id>/`: launch spec, `worker.pid`, `claude.pid`, `signal`, `heartbeat`, `last-session.json`, `exit.json`. Handoff counts, the idle check (unattended, 30 min) and the quick-exit check are per unit. Because the runner only watches files, a runner that dies leaves its sessions running; the next `roadmap execute` adopts the live ones, processes those that ended, and merges what is closed.

**Terminals.** Warp (checked 2026-10-07) can open a tab with a command only through Tab Configs: a TOML file in `~/.local/share/warp-terminal/tab_configs/` with `commands`, opened by `xdg-open warp://tab_config/<name>` (`?new_window=true` for a window). `warp://action/new_tab` takes no command; Launch Configurations are superseded; the binary's `warpctrl` local control (create tab, activate tab) is not enabled in the stable build. Two limits found by testing: Warp always focuses the new tab (no background option in the URI, the settings schema, or the actions), and it types the command into the tab's input, so a key the user presses at that moment breaks the command (the user hit this). A tab per unit would steal the keyboard every few minutes; returning focus with `ctrl+PageUp` (new tabs open after the current one by default, `general.new_tab_placement`) still flickers, which the user rejected. So, the user's choice: **fixed tabs, one per slot**, opened once when the run starts, last slot first so they end up in order next to the runner's tab. Each runs `roadmap slot`, which waits for the runner to assign a unit (`run/slots/<n>/assign`), runs the worker in the foreground, and goes back to waiting; it exits when the runner writes `quit` or the runner's lock is free. The runner opens each tab, waits until the window title becomes the tab's (xdotool; Warp runs on XWayland), sends `ctrl+PageUp` or re-activates the user's window, and checks that the slot process started; if not (a stray key), it opens the tab once more. The worker sets `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`, so the tab shows the unit, not "Claude Code".

Outside Warp, a parallel run opens one `gnome-terminal` window per session (the worker, which closes the window when it ends). `--terminal warp|gnome-terminal|inline` overrides the choice; `inline` runs one session at a time in the runner's terminal, the original behavior and the default for `parallel: 1`.
