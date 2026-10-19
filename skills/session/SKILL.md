---
name: session
description: Do one unit of a roadmap, in a session launched by the roadmap runner (`roadmap execute`). The runner starts every session with "/roadmap:session <roadmap> <unit>"; people do not call it.
argument-hint: <roadmap> <unit>
disable-model-invocation: true
---
# Roadmap session

!`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" brief $ARGUMENTS 2>&1`

## What this session is

The runner launched this session for **one unit**: the one above. You do that unit and nothing
else, then close it with one `roadmap` command. When your turn ends after that command, the
runner closes this session and starts the next one with a clean context. The next session
knows only what you wrote down: the unit file notes, the commits, and `roadmap.json`.

`roadmap` is a CLI on the PATH. It is the only thing that changes `roadmap.json`: never edit that
file by hand, and never touch the status of another unit.

## Rules

- **Worktree.** When the brief shows `Worktree:`, other sessions are working in parallel, each in
  its own worktree. Work, build, test and commit only inside yours, on its branch. Never check out
  another branch, merge (except a `Pending merge`), rebase, push, or touch the repo's own checkout
  (`Repo:`), even when `ROADMAP.md` mentions pushing: the runner merges your branch into the
  roadmap branch when the unit closes, and pushes if the roadmap says so.
- **The roadmap's rules come first.** `ROADMAP.md` above says the branch, the push policy, what is
  forbidden, and what "verified" means. Follow it over any default here.
- **Targeted reads.** Read the unit file (above) and what its "Leer antes" names. Do not read
  other units' files unless this one says so. Do not explore the repo broadly: grep and read excerpts.
- **No subagents**, unless `ROADMAP.md` allows them. Each subagent pays the fixed context again
  and rediscovers what this session already knows.
- **Commit when a piece is green**, not only at the end: a session that dies leaves its work behind.
- **Do not widen scope.** Anything outside the unit goes into the closing note as a finding.
- **Questions.** The plan asked the user everything up front; the "Decisiones" section holds
  the answers. For a minor gap, take the conservative option and record it as an assumption
  in the closing note.
  - `Mode: attended`: the user is watching. For a real blocker that the brief does not decide, you
    may ask in one `AskUserQuestion` call, recommended option first. Prefer blocking over a long
    conversation.
  - `Mode: unattended`: nobody is there. Never ask, never wait, never enter plan mode: **block**
    (below). The mode can change while you work. If a tool call is denied with "Unattended
    roadmap run", you are now unattended.
- **Context awareness.** A hook reports the context size as `[roadmap] Context …` at 60%, 80% and
  93% of the roadmap's limit. At 60%, plan the close. At 80%, decide: finish if the rest clearly
  fits, otherwise hand off or split. At 93%, stop new work and hand off. Never push past the
  limit hoping to finish.

## Steps

1. **Orient.** If the brief shows `Pending merge`, do that merge first, as it says. If the unit file has a `## Nota de traspaso`, `## Nota del runner` or answers from
   `/roadmap:attend`, start from them: check `git log --oneline -15` and `git status` against the
   note, and redo whatever it says was not committed.
2. **Documentador**, only when the brief shows `Documentador: project … · task …` (one line per
   task; `Documentador: off` means none). Each line says whose task it is and what this session
   does with it: **completes** it, or **only comments**. A task "of unit X, split" belongs to the
   whole unit X: this unit is one part of it, and the other parts share it. `start_task` on each
   task unless `get_task` shows it already in progress (an earlier part started it). If
   `ROADMAP.md` names who to assign it to, `update_task` with that assignee too.
3. **Read** what the unit names.
4. **Do the work**, following the unit's "Cómo" and the repo's own conventions (`CLAUDE.md`).
5. **Verify** with the unit's "Verificación" and the roadmap's rules. Red means not done: fix it,
   or hand off. Never close red.
6. **Commit**, and push only if `ROADMAP.md` says so and the brief shows no `Worktree:`.
7. **Close.**
   - Append `## Nota de cierre` to the unit file: commits, what was delivered, what was left out of
     the scope, assumptions you took, and what later units must know. Five to fifteen lines.
   - Documentador (if on): run `roadmap task` first. It recomputes the brief's line now, since
     units may have been split or added meanwhile. For each task it prints:
     - "only comments": `add_task_comment` with what this part delivered and what it left out.
       Never `complete_task`: other parts of the unit are still open.
     - "completes": `complete_task` with an output saying what was delivered and, above all, what
       was left out. For a task "of unit X", the output covers all of X: read the `## Nota de
       cierre` of X's other parts and sum up every part, not only this one.
   - Run `roadmap done` as the **last** tool call, then end the turn with a two-line summary.

## Handing off

When the unit does not fit this session (context, or it grew): commit what is green, then append
`## Nota de traspaso` to the unit file: what is done, what is next, what is not committed and must
be redone. Documentador (if on): `add_task_comment` with the same, on every task the brief lists. Then `roadmap handoff` as the
last tool call, and end the turn. The next session continues the same unit from your note. A
unit that hands off three times in a row is stopped (attended) or blocked (unattended).

## Splitting

When what is left is clearly more than one more session, split instead of handing off:

1. Commit what is green.
2. Append `## Nota de partición` to the unit file: what is done, and how the rest divides.
3. Run `roadmap split <unit> --children '[{"title": "…", "est_tokens": 70000}, {"title": "…"}]'`
   (optional `"model"` per child). It creates `<unit>.1`, `<unit>.2`, … in order, each depending
   on the previous one. Units that depended on this one now wait for all of them.
4. Fill in every brief it printed: Alcance, the Decisiones each part needs (copied in full), Leer
   antes, Cómo, Verificación. The next sessions start from those files alone.
5. Documentador (if on): `add_task_comment` on every task the brief lists, with what is done and
   the new parts. Never `complete_task`: the task stays in progress, and the parts carry it. Each
   part's brief tells its session whether it comments or completes; the last part completes it.
6. End the turn.

## Blocking

When the unit needs the user (a decision nobody wrote down, credentials, access, something only
a person can do): commit whatever is useful, append `## Nota de bloqueo` (what is done, what waits
on what), documentador `block_task` on every task the brief lists (a split unit's task waits on
this part too), then run as the last tool call:

```bash
roadmap block <unit> "<question>"
```

`/roadmap:attend` will put that question to the user later, without this session's context. Make
it self-contained: the situation in one sentence, the options, and your recommendation. The
runner goes on with the next unit that does not depend on this one.

## Never

- `roadmap execute`, `roadmap attend` or `roadmap unattend` (the user runs those).
- Closing a unit with red checks, or writing a note that claims more than was done.
- More work after a close command. After `done`, `handoff` or `block`, end the turn. After `split`,
  only fill in the new briefs, then end the turn.
