---
description: Review the current diff (or given code) against the delab coding principles.
argument-hint: "[optional: path, or leave blank to review the working diff]"
---

Review code for conformance to the Erlich lab (delab) coding principles.

First, read the principles and the relevant language file:

- Principles: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/SKILL.md`
- Language idioms: `${CLAUDE_PLUGIN_ROOT}/skills/delab-coding-practices/languages/<lang>.md`
  for whichever language(s) the code is written in.

Then determine what to review:

- If `$ARGUMENTS` names a path, review that file or directory.
- Otherwise review the current working diff (`git diff` and staged changes); if
  there is none, review the most recently changed source files.

Report findings as a list, most important first. For each finding give:

- `file:line`
- the **principle number and name** it violates (e.g. "principle 9 — fail loudly"),
- what's wrong and the concrete fix.

Be specific and actionable; do not rewrite the code in this command — that's what
`/delab-refactor` is for. If the code already follows the principles, say so
briefly rather than inventing nits. Explain the *why* behind each finding so the
author learns the reason, not just the rule (this is the skill's second goal).
