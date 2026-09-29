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
| `limits` | `five_hour` (wait for the reset), `weekly` (stop), `fable` (stop before a Fable unit). Percent of the plan limit. Defaults 95/70/90: the thresholds of the original runners, plus Fable. |
| `default_model` | `opus` |
| `documentador` | `null`, or `{"project_id": …}` when the user asked for it |
| `units[]` | `id`, `title`, `file`, `model`, `est_tokens`, `depends_on`, `status`, `task`; runtime: `started_at`, `finished_at`, `handoffs`, `sessions[]` (context at first and last reply, signal, transcript), `blocked` (`question`, `since`), `history[]`, `children`, `parent` |

Statuses: `pending`, `in_progress`, `done`, `blocked`, `split`. A split unit's dependents wait for all its children. `depends_on: ["*"]` waits until every other unit is done, blocked, or stuck behind a blocked unit: the Farmagram "final" unit, generalized (plan 4 of Farmagram lost its final test run because the last unit blocked and nothing owned the run).

JSON, not a markdown table: the Farmagram runner counted states with a regex over `INDEX.md`, which breaks on a hand edit. Sessions change state only through the CLI (`done`, `handoff`, `block`, `split`, `set`), which validates and writes atomically under a `flock`. Briefs stay markdown, because people and models read them.

The runner picks the unit, not the session. It needs the unit before launching, to pass `--model`, and the choice is deterministic: first `in_progress`, else first `pending` whose dependencies are met, in file order.

## 3. The runner

`roadmap execute` is the loop from the original runners, in Python:

1. Validate, pick the unit, check usage (below), mark it `in_progress`.
2. Launch interactive `claude --model <m> --dangerously-skip-permissions "/roadmap:session <name> <unit>"` with `ROADMAP_RUNNER=1`, `ROADMAP_DIR`, `ROADMAP_UNIT`, `ROADMAP_RUNNER_PID`. Session variables of any enclosing Claude Code session (`CLAUDECODE`, `CLAUDE_PID`, …) are stripped.
3. The session closes its unit with a CLI command, which writes `run/signal`. The Stop hook sees it when the turn ends and SIGTERMs the `claude` process: the runner's direct child, found by walking up from the hook. It waits 2 s first, so the last message is painted.
4. The runner reads the signal: `next` (done or split), `continue` (handoff; three in a row stop the run when attended, block the unit when unattended), `blocked` (go on with the next eligible unit).

Why a new process: nothing can run `/clear` for the model (checked for the handoff plugin, DESIGN.md §6 there), and `claude -p` hides the session. The user wants to watch and to talk to a session.

Ctrl+C: while a session runs, the runner's SIGINT handler is a Python function, which `exec` resets to the default, so the session still handles Ctrl+C and the runner survives. `SIG_IGN` would be inherited and break Ctrl+C in the session. During the pause between sessions, Ctrl+C stops the runner. Quitting a session yourself stops it too, in attended mode: no signal means someone intervened.

A session that ends without a signal in under 45 s never reached its unit: the folder trust dialog answered "No" (its default), an unknown model, no login. The runner stops instead of retrying. Found in the first end-to-end test, where the unattended runner blocked three units in 20 seconds.

`/roadmap:execute` cannot host the runner, because the runner must be the parent of every session. It opens a new `gnome-terminal` with `roadmap execute`, with the session variables stripped. The same name works in the terminal: `roadmap execute`.

## 4. Usage limits

Before each session the runner reads `https://api.anthropic.com/api/oauth/usage` with the OAuth token of `~/.claude/.credentials.json`, the endpoint `/usage` uses. The `limits` array has `kind: session` (5 hours), `weekly_all`, and `weekly_scoped` with `scope.model.display_name: "Fable"`. Older fields `five_hour` and `seven_day` are the fallback. If usage cannot be read, the runner goes on, as the original runners did. The limits are absolute thresholds, the user's choice on 2026-09-29, not a budget relative to the roadmap's start.

## 5. Context awareness

A `PostToolUse` hook reads `transcript_path` and takes the usage of the last main-thread assistant reply: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, the same measure the handoff status line uses. That is the context the next request carries. When it crosses 60%, 80% or 93% of `context_limit`, the hook returns `additionalContext` with the size and what to do: plan the close; decide between finish, hand off and split; stop new work. Past 93% it repeats every fifth tool call. It stays quiet otherwise, so it costs nothing until it matters.

The model decides, because only it knows how much of the unit is left. The CLI gives it the three exits: `handoff` (same unit, next session, from a Nota de traspaso), `split` (children `<id>.1…`, each depending on the previous, briefs it fills in), and `done`.

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

Session rules default to the lessons of the original skills: no subagents (each pays the fixed context again; a 30-hour Farmagram run with subagents exhausted the account), targeted reads, commit when green, never close red, findings go to the closing note. `ROADMAP.md` can override them.

## 8. Hooks

All hooks go through `scripts/hook.sh`, which exits at once unless `ROADMAP_RUNNER=1`. Normal sessions, and hand-opened sessions in a repo with a roadmap, are never touched. Inside a runner session the Python handler catches everything and always exits 0: a hook must never break a session. No network in hooks.

## 9. The CLI outside Claude

Claude Code puts a plugin's `bin/` on the Bash tool's PATH, not on the user's terminal PATH. `roadmap install-cli` writes `~/.local/bin/roadmap`, a shim that reads `~/.claude/plugins/installed_plugins.json` and runs the installed version's `bin/roadmap`, so it follows plugin updates. It falls back to the copy that installed it.
