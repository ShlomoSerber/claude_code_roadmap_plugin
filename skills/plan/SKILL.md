---
name: plan
description: Plan a roadmap. Turns a batch of tasks into units that each fit one session, written in the roadmap schema, with a model per unit and usage limits. Asks every question up front so the run never needs the user. Manual only; never auto-invoke.
argument-hint: [roadmap name] [the tasks, or nothing to be asked for them]
disable-model-invocation: true
---
# /roadmap:plan

Context (computed, do not recompute):
- Repo: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Roadmaps here: !`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" list 2>&1`
- `roadmap` CLI on PATH: !`command -v roadmap || echo "missing: run \"${CLAUDE_PLUGIN_ROOT}/bin/roadmap\" install-cli"`
- Account usage now: !`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" usage 2>&1`
- Fixed context of a session in this repo: 
!`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" baseline 2>&1`
- Unit brief template: `${CLAUDE_PLUGIN_ROOT}/templates/unit.md`
- The user's request: $ARGUMENTS

## What you are building

A roadmap is a list of **units** that a runner (`roadmap execute`) does one per session. Each
session starts from zero context, gets `ROADMAP.md` and its own unit file, does the unit, and
closes it. Nobody carries context between sessions except these files and the commits.

**The goal of this planning session: the run must never need the user.** Every question a
session could have must be asked now, and every answer written into the unit that needs it.
The user may leave the run unattended overnight. A question you skip now becomes a blocked unit
in the morning.

Files, in `<repo>/.claude/roadmaps/<name>/` (kept out of git through `.git/info/exclude`):

| File | Content |
|---|---|
| `roadmap.json` | The state. You write it now; after that only the `roadmap` CLI changes it. |
| `ROADMAP.md` | Goal and the rules every session follows. Short: every session reads it. |
| `units/<id>-<slug>.md` | One brief per unit, from the template: Qué es, Alcance, Decisiones, Leer antes, Cómo, Verificación, Cierre. |

`roadmap.json`, after `roadmap init` creates it:

```json
{
  "schema": 1, "name": "auth-rework", "title": "…", "created": "YYYY-MM-DD",
  "mode": "attended", "permission_mode": "bypass", "context_limit": 150000,
  "limits": {"five_hour": 95, "weekly": 70, "fable": 90},
  "default_model": "opus", "documentador": null,
  "units": [
    {"id": "01", "title": "…", "file": "units/01-slug.md", "model": "opus",
     "est_tokens": 70000, "depends_on": [], "status": "pending", "task": null}
  ]
}
```

- `id`: short, ordered (`01`, `02a`, `02b`). **The order of `units` is the order of execution**; a
  session takes the first pending unit whose `depends_on` are done.
- `depends_on`: unit IDs, or `["*"]` for a unit that runs after every other unit is done or
  blocked (a deferred full test run, for example). At most one such unit.
- `model`: `opus`, `sonnet`, `haiku`, `fable`, or a full model ID.
- `est_tokens`: your estimate of the context the unit's session reaches.
- `task`: documentador task ID, or `null`.

## Steps

### 1. Name and intake

Take the tasks from the request. If there are none, ask the user to list them all, in their
own words, and wait. Pick a short kebab-case name for the roadmap and confirm it with the
title.

### 2. Understand enough to size and to find the decisions

Read `CLAUDE.md` (already loaded) and explore only what you need to split the work and to
spot undecided behavior. Use at most two Explore subagents. This session has the same
context budget as the rest: if it grows past ~100k, write what you have to the files and
continue from them.

### 3. Draft the units

A unit is one session that ends green and committed. Size them:

- **Room per session** = `context_limit` minus the fixed context above. Aim `est_tokens` at 60% of
  the room or less. The rest is margin for surprises, verification and the close.
- Rough costs: reading a 300-line file ≈ 4-5k tokens; each edit, test run or build adds its
  output; one medium feature touching 3-6 files with tests ≈ 50-90k.
- Split a task when it has more than one of: a schema change with its migration; a new screen
  or a large rework of one; a change in a hot path with its own test scenarios; an importer or
  seed rework; an end-to-end flow of its own. Split by what can be committed green alone,
  backend before frontend.
- If test suites are deferred to the end, that run is a unit of its own with `depends_on: ["*"]`.
  A sentence saying "tests at the end" has no owner.

Show the user the draft (ID, title, estimate, dependencies) before the interview. They may
merge, split or reorder.

### 4. The interview

Walk this checklist for the roadmap and for every unit. Ask what the code and the docs do not
answer. Use `AskUserQuestion`: up to four questions per call, recommended option first, as many
rounds as needed. Group by theme. Open questions (names, texts, criteria) go in chat.

**Roadmap-wide** (these go into `ROADMAP.md` → "Reglas de todas las sesiones"):
- Branch; commit policy; push or not; PR or direct. Merges and deploys are forbidden unless the
  user says otherwise.
- What "verified" means: which lint, test and build commands; which suites run per unit and
  which only at the end.
- Forbidden or outward-facing actions: migrations on shared databases, emails, publishing,
  paid APIs.
- Assumption policy: what a session may decide alone.
- Subagents: the default is no.

**Per unit** (these go into the unit's "Decisiones", in full):
- Scope: what is in, what is out, concrete acceptance criteria.
- Behavior the code does not decide: edge cases, errors, texts and copy, what happens to existing
  data.
- External needs: credentials, env vars, accounts, VPN, running services, test data, access to
  another repo. Anything missing now either gets solved now or becomes an explicit prerequisite
  in the brief, so the session blocks early and cleanly.
- Verification: the exact commands, and whether it needs a browser, an emulator or the display.

**Readiness test.** For each unit, ask yourself: *could a fresh session with only `ROADMAP.md`
and this unit file do it without asking anything?* If not, ask more.

### 5. Models

The default is `opus` for every unit. Suggest another model only where it clearly fits:
`sonnet` for mechanical work (renames, doc sweeps, config); `fable` for the hardest units
(architecture, deep debugging), noting that they consume the Fable limit. Put the suggestions in
one question and let the user confirm or change them.

### 6. Limits

Show the account usage above. Ask for the three limits in one `AskUserQuestion` call, with
these recommended values first:

- **5 horas: 95%.** At this level the runner waits for the window to reset, then continues.
- **Semanal: 70%.** At this level the runner stops.
- **Fable: 90%.** The runner stops before a Fable unit at this level. It only matters if some
  unit uses Fable.

The context limit per session is 150k tokens unless the user says otherwise. Sessions run
with `--dangerously-skip-permissions` (`"permission_mode": "bypass"`), which unattended runs
need. Mention both in the final summary; ask only if the user brings them up.

### 7. Documentador: only when the user asked for it

Use the documentador **only if the user explicitly asked, in this conversation**, to create the
tasks there. Otherwise do not create tasks, and do not offer to. If they asked:

- Find the project (`list_projects`, `get_project_context`).
- Create one task per original task and one subtask per unit (`create_task`,
  `create_subtasks`). Put the decisions in the descriptions.
- Set `"documentador": {"project_id": <id>}` in `roadmap.json` and each unit's `"task"`. If
  the user wants the tasks assigned to someone, write that in `ROADMAP.md`.

### 8. Write the roadmap

1. If the CLI is missing, run the `install-cli` command shown above.
2. `roadmap init <name> --title "<title>"`.
3. Write `ROADMAP.md`: goal, the rules from the interview, and the order rationale in a few lines.
4. Write one unit file per unit from the template. "Leer antes" names concrete paths: it
   replaces exploration. "Decisiones" carries the answers in full: do not point to this
   conversation, the session will never see it.
5. Fill `units` in `roadmap.json`.
6. `roadmap validate`, and fix until it passes. Then `roadmap status`.

### 9. Hand over

Show the `roadmap status` table and one line with the limits. Then tell the user, in their
language:

- The plan is ready. Close this session and run `roadmap execute` in `<repo>` (or
  `/roadmap:execute` to open it in a new terminal).
- If they will not be around: `roadmap unattend` before starting, or `/roadmap:unattend` in the
  running session. `/roadmap:attend` later answers whatever got blocked.

Do not start executing units in this session.
