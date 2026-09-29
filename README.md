# Roadmap — a Claude Code plugin

When many tasks arrive at once, one long session gets expensive: every tool call re-reads the whole context, and the context keeps growing. Roadmap splits the work into **units** that each fit one session, then runs them as a chain of **fresh interactive sessions**, one unit per session, with no one watching the context or typing `/clear`.

```
/roadmap:plan        plan the roadmap: units, decisions, a model per unit, usage limits
roadmap execute      run it: one fresh session per unit, in this terminal
/roadmap:unattend    nobody is around: sessions block instead of asking, the run goes on
/roadmap:attend      back: answer what got blocked, then run `roadmap execute` again
```

## What it adds over Claude Code's plan mode

Plan mode plans one change and executes it in the same session. Roadmap is for a batch of tasks:

- **A schema.** `roadmap.json` holds units with status, dependencies, model and token estimate. A CLI changes it, so the runner never breaks on a hand-edited table.
- **One session per unit.** Each session starts from zero context and reads only `ROADMAP.md`, its unit brief and what the brief names.
- **A model per unit.** The runner launches each session with `--model <unit's model>`. The default is `opus`.
- **Usage limits between sessions.** Before each session the runner reads the plan usage `/usage` shows. At the 5-hour limit it waits for the reset; at the weekly limit it stops; at the Fable limit it stops before a Fable unit.
- **Context awareness inside a session.** A hook tells the session its context size at 60%, 80% and 93% of the limit (150k by default). The session then closes, hands off to a new session, or splits the unit.
- **Unattended mode.** Hooks deny questions and plan mode, and refuse to let a session stop with its unit open. What needs you is blocked with a self-contained question; the run goes on with the next unit.
- **Documentador, on request only.** If you ask for it while planning, the units become tasks and subtasks, and sessions move them.

## Usage

### 1. Plan

In a session in the repo:

```
/roadmap:plan auth-rework after the meeting: fix the login redirect, add SSO, move sessions to Redis...
```

Claude drafts the units, then interviews you until every unit could run without asking anything: scope, behavior, credentials, branch and push policy, verification commands. It also asks for a model per unit (default `opus`) and the three limits. It writes the roadmap in `<repo>/.claude/roadmaps/<name>/` (kept out of git through `.git/info/exclude`), then tells you to close the session.

### 2. Execute

In a terminal, in the repo:

```bash
roadmap execute              # the only open roadmap
roadmap execute auth-rework  # a named one
roadmap execute -- --add-dir ../other   # extra claude arguments after --
```

Or `/roadmap:execute` from a session, which opens the runner in a new `gnome-terminal` window.

Each session is a normal interactive Claude Code session, full screen. You can watch it, and Ctrl+C talks to it as usual. When the unit is closed, the session ends by itself and the next one starts after a 15-second pause. Ctrl+C during the pause stops the runner. Quitting a session yourself also stops the runner: no close signal means someone intervened.

The repo folder must be trusted in Claude Code before the run: open `claude` in it once. A session that ends within 45 seconds without closing its unit (trust dialog, unknown model, not logged in) stops the runner instead of burning units.

Sessions run with `--dangerously-skip-permissions` (`permission_mode` in `roadmap.json`: `bypass`, `auto`, `acceptEdits`, `default`). Unattended runs need `bypass` or `auto`, because a permission dialog would wait for you all night.

### 3. Leave it running

```bash
roadmap unattend          # before starting, from a terminal
/roadmap:unattend         # or typed into the running session
```

From then on, no session asks or waits. A minor gap becomes an assumption written in the closing note. A real blocker becomes a blocked unit with a question. The runner goes on with every unit that does not depend on it. A session that stays idle for 30 minutes is closed and retried. A unit that hands off three times in a row is blocked with a question about how to split it.

### 4. Come back

```
/roadmap:attend estoy, preguntame lo que necesites
```

Claude switches the roadmap back to attended mode and shows what was done and what is blocked. It asks you every pending question, writes the answers into the unit briefs, and unblocks the units. Then run `roadmap execute` again.

### Other commands

```bash
roadmap status     # units, states, estimated vs real context per unit
roadmap list       # roadmaps in this repo
roadmap usage      # 5 hour · weekly · Fable usage now
roadmap blocked    # blocked units and their questions
roadmap set 03 model=sonnet    # change a unit (title, model, status, est_tokens, depends_on, task)
```

## Files

```
<repo>/.claude/roadmaps/<name>/
  roadmap.json     state: units, mode, limits, context limit, documentador
  ROADMAP.md       goal and the rules every session follows (branch, push, verification, forbidden)
  units/<id>-*.md  one brief per unit; sessions append Nota de cierre / traspaso / partición / bloqueo
  run/             signal, heartbeat, hook state, runner.log
```

## Install

Local directory marketplace, user scope:

```bash
claude plugin marketplace add "/path/to/claude_code_roadmap_plugin"
claude plugin install roadmap@roadmap
```

Then install the `roadmap` command for your terminal. It writes a small shim to `~/.local/bin/roadmap` that always runs the installed plugin's copy:

```bash
python3 /path/to/claude_code_roadmap_plugin/bin/roadmap install-cli
```

`/roadmap:plan` and `/roadmap:execute` install it too if it is missing.

Requirements: Linux, `python3`, `git`, Claude Code logged in with a Claude subscription (usage limits come from `~/.claude/.credentials.json`). `gnome-terminal` only for `/roadmap:execute`.

## How it works

See [DESIGN.md](DESIGN.md).
