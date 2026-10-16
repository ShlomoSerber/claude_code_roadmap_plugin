---
name: execute
description: Start the roadmap runner in a new Warp tab or terminal window, so the roadmap runs as fresh sessions, several at a time when the roadmap allows it. The same as running `roadmap execute` in a terminal. Manual only; never auto-invoke.
argument-hint: [roadmap name] [-- extra claude arguments]
disable-model-invocation: true
---
# /roadmap:execute

Context (computed, do not recompute):
- `roadmap` CLI on PATH: !`command -v roadmap || echo "missing"`
- Validation: !`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" validate $ARGUMENTS 2>&1 | head -30`
- Status: 
!`"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" status $ARGUMENTS 2>&1 | head -60`
- Arguments: $ARGUMENTS

The runner launches and watches every session, so it cannot run inside this one. This command
opens it in a new Warp tab (when this session runs in Warp) or a new `gnome-terminal` window.

1. If the CLI is missing, run `"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" install-cli`.
2. If validation failed, show the problems and stop. `/roadmap:plan` or the `roadmap set`
   command fixes them.
3. If the status shows no unit left to do, say so and stop. If the only units left are
   blocked, suggest `/roadmap:attend` and stop.
4. Run `"${CLAUDE_PLUGIN_ROOT}/bin/roadmap" execute <name> --new-terminal`, with the roadmap name
   from the arguments if given. Pass extra claude arguments after `--`. It waits until the runner
   starts (up to 30 s). If it fails, show its message and the command to run by hand:
   `cd <repo> && roadmap execute <name>`.
5. Tell the user, in their language, in three lines at most: the runner is open in a new tab or
   window; each unit runs in its own session with the model of the unit and with permissions
   skipped (with parallel > 1, in fixed tabs the runner opens next to its own, each session in its
   own worktree); they can close this session. If neither Warp nor `gnome-terminal` is there,
   give them the command to run by hand: `cd <repo> && roadmap execute <name>`.

Do not do any unit's work in this session.
