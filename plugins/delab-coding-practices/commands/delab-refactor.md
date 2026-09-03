---
description: Refactor the given code to follow the delab coding principles, explaining each change.
argument-hint: "[path or a description of the code to refactor]"
---

Refactor code to follow the Erlich lab (delab) coding principles.

First, read the principles and the relevant language file:

- Principles: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/SKILL.md`
- Language idioms: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/languages/<lang>.md`
  for the language the code is written in.

Then refactor the target in `$ARGUMENTS` (a path, or the code the user points
to). Apply the principles from `SKILL.md` — prioritise the ones the code
actually violates rather than touching everything — and follow the *before →
after* idioms in the language file.

How to go about it:

- Work in small, reviewable steps, on a feature branch (principle 12).
- Preserve behavior. Where practical, add or run a test first (principle 6,
  synthetic fixtures) so you can show the refactor is behavior-preserving.
- Don't touch unrelated code.
- For each change, briefly explain *which principle* it serves and *why* — the
  goal is that the author learns the reasoning, not just the rule.
