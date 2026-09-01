---
description: Refactor the given code to follow the delab coding principles, explaining each change.
argument-hint: "[path or a description of the code to refactor]"
---

Refactor code to follow the Erlich lab (delab) coding principles.

First, read the principles and the relevant language file:

- Principles: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/SKILL.md`
- Language idioms: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/languages/<lang>.md`
  for the language the code is written in.

Then refactor the target in `$ARGUMENTS` (a path, or the code the user points to):

- Split I/O, analysis, and plotting into separate functions (principle 8); make
  the analysis layer pure (principle 2).
- Replace hand-rolled index loops with `map`/vectorization where it reads better
  (principle 4), and break large functions into small, named ones (principle 5).
- Add cache-or-compute where a step is expensive (principle 3), fail loudly on
  bad input instead of returning silent defaults (principle 9), and lift secrets
  and hard-coded paths out of the source (principle 7).
- Keep comments about the present, not the history (principle 10).

Work in small, reviewable steps. Preserve behavior: where practical, add or run a
test (principle 6, synthetic fixtures) to confirm the refactor is behavior-
preserving. For each change, briefly explain *which principle* it serves and
*why* — the goal is that the author learns the reasoning. Do not touch unrelated
code, and do the work on a feature branch (principle 12).
