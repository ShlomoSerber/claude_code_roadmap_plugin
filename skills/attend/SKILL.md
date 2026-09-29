---
name: attend
description: Back from an unattended run. Switches the roadmap to attended mode, puts to the user every question the blocked units left, writes the answers into their briefs and unblocks them, so the next `roadmap execute` can go on. Manual only; never auto-invoke.
argument-hint: [roadmap name] [anything the user adds]
disable-model-invocation: true
---
# /roadmap:attend

Context (computed, do not recompute):
- Mode: !`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" attend 2>&1`
- Status:
!`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" status 2>&1 | head -60`
- Blocked units:
!`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" blocked 2>&1`
- Last runner events:
!`tail -n 15 "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"/.claude/roadmaps/*/run/runner.log 2>/dev/null`
- The user's words: $ARGUMENTS

If the lines above say there are several roadmaps, take the one the user's words name, or ask
which one. Then run `roadmap attend <name>`, `roadmap status <name>` and `roadmap blocked <name>`
yourself.

## Steps

1. **Report.** In a few lines: what the run finished, what is blocked, and what waits on the
   blocked units.
2. **Understand each block.** Read the unit file's `## Nota de bloqueo` (and `## Nota del runner`
   if present) before asking. The stored question is the session's summary. Check it against
   the note, and ask the real question.
3. **Ask.** Use `AskUserQuestion`: up to four questions per call, recommended option first,
   grouped when they are related. Open answers (texts, names, criteria) go in chat. A unit that
   handed off too many times asks how to split it or what is in the way.
4. **Write the answers** into each unit file, under `## Respuestas (<date>)`, in full, as
   decisions a fresh session can follow without this conversation. If an answer changes the
   scope, update "Alcance" and "Decisiones" too.
5. **Apply them.**
   - Unblock: `roadmap unblock -r <name> <unit>`.
   - Split instead: `roadmap unblock`, then `roadmap split -r <name> <unit> --children '[…]'`, and
     fill in the new briefs.
   - Drop the unit: append a `## Descartada` note with the user's reason, then
     `roadmap unblock -r <name> <unit>` and `roadmap set -r <name> <unit> status=done`.
   - Documentador (if the unit has a task): `unblock_task`, and a comment with the answer.
6. **Hand back.** Show `roadmap status`. Tell the user to close this session and run
   `roadmap execute` (or `/roadmap:execute`). The roadmap stays attended until they run
   `roadmap unattend` again.

Do not do any unit's work in this session.
