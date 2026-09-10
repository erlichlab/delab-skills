---
description: Load the lab's agentic workflow (the PM, worker and reviewer roles, issue-driven development, and why reviews are separated) into context and follow it from here on.
argument-hint: "[optional: which role you are playing — worker or reviewer]"
---

Read now:

- The agentic workflow: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/guides/agentic-coding-for-agents.md`
- How the PI expects to be involved: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/guides/agentic-coding-for-humans.md`

If the delab coding principles are not already in context, read those too:
`${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/SKILL.md`.

Then work to that guide for the rest of this session. Identify which role you
are playing and follow **that role's section** — the roles have different duties,
and most of the guide will not apply to you:

- `$ARGUMENTS` names your role if it is given.
- Otherwise infer it: you are the **worker** if you are implementing a work item,
  and the **reviewer** if you are checking work you did not write.

The one rule that binds every role: code is reviewed by something that did not
write it. If you wrote it, say so and ask for a fresh reviewer rather than
reviewing it yourself.

This command loads the workflow; it does not put you in charge of one. To take
the **PM** role — decomposing a goal into issues, gating complex plans on the
PI's confirmation, and delegating to the `delab-coder` and `delab-reviewer`
subagents — use `/delab-enforce-style`, which is built for it.
