---
name: unattend
description: Switch a roadmap to unattended mode. From now on no session may ask anything or wait for a person. A unit that needs the user gets blocked with its question, and the run goes on with the next unit. Manual only; never auto-invoke.
argument-hint: [roadmap name]
disable-model-invocation: true
---
# /roadmap:unattend

Result (already applied): !`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" unattend $ARGUMENTS 2>&1`
Runner session: !`[ "${ROADMAP_RUNNER:-}" = "1" ] && echo "yes, unit ${ROADMAP_UNIT:-?}" || echo no`

If the result is an error, show it and stop.

Otherwise confirm in one line, in the user's language: unattended mode is on for the whole
roadmap. Sessions will not ask. What needs the user gets blocked with its question, and
`/roadmap:attend` answers those later.

If this is a runner session, from now on:
- Never call `AskUserQuestion` or enter plan mode, and never end a turn waiting for an answer.
  A hook now denies those tools and refuses to let the session stop with the unit open.
- For a minor gap, take the conservative option and note it as an assumption in the closing note.
  For a real blocker, block the unit as the `session` skill says (`roadmap block <unit> "<question>"`).
- Then continue the unit where you left it.
