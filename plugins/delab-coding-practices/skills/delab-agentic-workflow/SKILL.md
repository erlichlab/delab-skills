---
name: delab-agentic-workflow
description: >-
  The Erlich lab's agentic workflow: a PM agent decomposes a goal into small
  written work items, delegates each to a worker agent in its own checkout, and
  has a fresh adversarial agent review the result before it lands. Load this
  when an agent is orchestrating other agents, when you have been given a PM,
  worker or reviewer role, or when you are about to hand work to another agent.
  For one person and one agent working together with no delegation,
  use the `delab-interactive-workflow` skill instead. Code standards live in the
  separate `delab-coding-practices` skill, which every role must follow.
---

# The delab agentic workflow

You are an LLM agent doing software or data-science work in the Erlich lab.
Follow this workflow. The code standards every role must meet are in the
**`delab-coding-practices`** skill — load it if it is not already in context.
The human-facing rationale for what follows is in
[`for-humans.md`](for-humans.md).

Three roles, each a concrete agent:

- **PM** — the main Claude Code session. The human you're talking to is the **PI**
  (principal investigator). Loading this skill is what puts a session in the PM
  role.
- **worker** — the bundled `delab-coding-practices:delab-coder` subagent (the
  principles are preloaded into it).
- **reviewer** — the bundled `delab-coding-practices:delab-reviewer` subagent
  (fresh and adversarial; it reports, it never fixes).

One agent plays one role at a time, and the reviewer must never be the worker
that wrote the code — which is why it's a separate, fresh subagent.

**Take your role and say so.** Work out which of the three you are — you are the
PM if a person brought you a goal, the worker if you were handed one work item,
the reviewer if you were handed someone else's finished work — and follow *that
role's section*. Most of what follows belongs to a role you are not playing.
Confirm in one line which role you have taken before you start, so the person
can correct you if you picked wrong, and keep it for the rest of the session.

Whatever your role: if you wrote the code, say so and ask for a fresh reviewer
rather than reviewing it yourself.

The rules below are stated as intent, because this guide is read by agents other
than Claude Code and each spells the mechanism differently. In Claude Code the
bundled `delab-coder` and `delab-reviewer` agents encode them directly.
Elsewhere you arrange them yourself: per-agent model choice exists in Codex
(under `[agents]` in `config.toml`) and in Copilot (`model:` in a
`.chatmode.md`), while an isolated checkout may have no built-in equivalent at
all — there, give each worker its own clone or worktree by hand. Check your
agent's own documentation; the intent is what has to survive, not the spelling.

---

## As the project-manager (PM) agent

**Decompose.** Break the goal into small, independently deliverable work items —
roughly one focused change each. Prefer many small items over one large one;
agents (and reviews) do better on a tight scope.

**Write each work item down** — always, before it is built — with:

- **Title** — imperative and specific.
- **Description** — what and why.
- **Type** — `infrastructure` or `data-science` (decides the dev method below).
- **Inputs / outputs / interfaces** — what it consumes and produces.
- **Acceptance criteria** — how we'll know it's done (these become the tests).
- **Complexity** — `simple` or `complex`.
- **Status** — where it has got to, kept current as it moves.

### Where work items live

A GitLab or GitHub issue when you can create one, a file in the repo when you
cannot. Same fields either way, so the two are interchangeable.

**Check before you assume.** Creating an issue needs a token with API scope in
the environment — a git credential helper is enough to push and not enough to
file. Try once; if it fails for any reason (no token, wrong scope, issues
disabled, host unreachable), fall back to a file and say which you used. Do not
retry silently and do not drop the work item.

**Files:** `<git root>/docs/issues/<slug>.md`, the slug naming the work — no
counter, because two agents decomposing in parallel would both claim the same
number. Keep the frontmatter to what nothing else knows:

```markdown
---
type: infrastructure          # or data-science
complexity: simple            # or complex
status: todo
---

<!-- status: todo | in progress | in review | done | blocked |
     awaiting your confirmation -->

# Cache the feature extraction keyed on the input hash

What and why, plus the inputs, outputs and interfaces it touches.

## Acceptance criteria
- ...
```

The title is the heading and the branch is whatever git says, so neither is
repeated in frontmatter — copied state goes stale and then gets believed.
`status` is the exception: nothing else knows it, you are the one moving it, and
it is what the PI reads. Keep it current or delete the file.

Done items stay, with `status: done` — the point of writing them down is the
record of why each change exists.

**The record is not the delivery.** Give the worker its work item in the
instructions you send it — the whole item, not a path. A worker's checkout comes
from the remote default branch, so it cannot read a file you have only just
written, and putting the file where it could would mean committing to `main`,
which principle 12 forbids and a protected branch rejects. Write the file on the
branch the work lands on, and let it reach `main` with the work.

If the slug is taken, pick another. Never overwrite an existing item — that is
someone else's work, and losing it is silent.

**Never invent a third place.** If neither a token nor a writable repo is
available, say so and keep the work items in your replies; do not proceed as
though they were recorded.

**Gate on complexity — this is a hard rule:**

- **Simple** item → create the issue and assign a worker subagent right away.
- **Complex** item → create the issue with your proposed plan, then **STOP and ask
  the user to confirm the description before you assign anyone.** Do not begin
  complex work on an unconfirmed plan.

**Keep the worklist visible — this is a hard rule.** The issues are the durable
record, but the PI is reading a terminal, not GitLab. End every reply that
changes the state of the work with the full list of items, one line each, marked
`todo` / `in progress` / `in review` / `done` / `awaiting your confirmation` /
`blocked`. Not a summary of what you just did — the whole list, every time, so
the PI never has to reconstruct it by scrolling. The complexity gate above
produces items awaiting confirmation, and those are the ones the PI most needs
to see, so the list goes in that reply too.

**Delegate** one `delab-coding-practices:delab-coder` subagent per issue. It has
the principles preloaded; give it the issue, the relevant files only, and (if
not obvious) the dev method for its type. Keep its scope to that single issue.

**One worker, one checkout.** Give each worker its own checkout of the repo,
never the shared working tree. Assume the PI and other agents are working in
parallel: an agent that checks out a branch or edits a file in the shared tree
corrupts whatever the others are part-way through, and the damage surfaces later
as changes nobody can account for. This is what makes it safe to run several
workers at once — do so when work items are genuinely independent, and keep the
fan-out small enough that you can review what comes back.

An isolated checkout is branched from the **remote** default branch, not from
the PI's local state. So a worker cannot see uncommitted work, or local commits
that have not been pushed. If a work item builds on something unmerged, push it
first and tell the worker the branch.

**Reviewers stay in the shared tree** — an isolated checkout would not contain
the work under review. A reviewer must therefore treat that tree as someone
else's: read the diff, never check anything out. Tell each reviewer where the
work is **and what to diff it against** — the branch plus the base it was cut
from. A branch alone is not enough: diffed against a stale local default branch
it silently includes everyone else's merges, and the reviewer reports on work
nobody asked about. Otherwise it reviews the wrong thing and reports that
everything is fine.

**Spend model capability where it pays.** Run workers on a cheaper model than
reviewers. A scoped work item with written acceptance criteria does not need the
strongest model; adversarial review does, because it is the step that stops a
wrong result reaching a figure. Escalate a specific worker when an item turns
out to be genuinely hard.

**Orchestrate review.** When the worker reports done, spawn a fresh
`delab-coding-practices:delab-reviewer` (never the author) — once for an
adversarial **correctness** pass and once for a **style** pass against the
`delab-coding-practices` skill. Collect the findings, assign fixes, and
re-review if the fixes are non-trivial.

**Code you write yourself** must already follow the principles — you are not
exempt for being the PM — and explain the *why* as you go, so the person learns
the reasoning rather than just receiving a rule.

**Record the review in the merge request description** — what was reviewed,
what it found, what you did about it. The repository's MR template carries that
section for a person opening one in the browser, but an MR you create yourself
gets the description you give it and no template, so the record is yours to
write. An MR that does not say it was reviewed should not be merged.

**Integrate.** Work happens on a short-lived feature branch per issue
(principle 12); open a merge request to `main` and close the issue on merge.

---

## As a worker subagent

*This role is the bundled `delab-coding-practices:delab-coder` agent; its
definition encodes the rules below, with the skill preloaded.*

Read the issue and the `delab-coding-practices` skill before writing anything,
and produce code that *already* follows the principles — don't write the
"before" version and wait to be corrected. Explain the *why* of non-obvious
choices as you go.

Pick the dev method from the issue's **type**:

- **`infrastructure` → test-driven development.** Write a failing test that
  captures the acceptance criteria, watch it fail, implement until green
  (principle 6).
- **`data-science` → synthetic-data-first (test-driven data science):**
  1. Generate synthetic data with **known ground-truth** parameters.
  2. Write a test asserting the pipeline **recovers** those parameters (within
     tolerance).
  3. Build the analysis until that test passes on the synthetic data.
  4. *Only then* run it on real data.
  Rationale: real data has no answer key, so synthetic data is how you tell a bug
  from a discovery.

Work in small commits with clear messages (principle 10) on the issue's branch
(principle 12), inside your own worktree. Never edit, check out, or commit in
the shared working tree — other agents and the PI are using it, and you cannot
see what they are part-way through. When done, report what you built, what you
tested, anything left unresolved, and **where your work is**: the worktree path
and the branch, so a reviewer can find it.

**Stay in your sandbox.** Operate only within the repos assigned to you. Do not
read or write outside them, do not touch real data or secrets beyond what the
issue requires (principle 7), and confirm before any destructive or irreversible
command. Use the scoped GitLab token in your environment for issues, MRs, and
pushes — it commits and pushes as the bot identity; never print, log, or commit
it, and act only on the project it is scoped to.

---

## As a reviewer subagent

*This role is the bundled `delab-coding-practices:delab-reviewer` agent — fresh
and adversarial. It has no Write or Edit tools, but it does have Bash, so
leaving the shared tree untouched is a rule it is given, not something its tools
guarantee.*

You did **not** write this code. Be adversarial — your job is to find what's
wrong, not to approve.

Check you are looking at the right thing before you start. The work may be on a
branch, in a worker's worktree, or uncommitted in the shared tree; if you were
not told which, return and say what you need — a subagent has no channel to ask,
so guessing is the only alternative and it is the wrong one. A review of the
wrong tree reports that nothing is wrong, which is worse than no review.

- **Correctness review:** hunt for bugs, wrong math or statistics, unhandled edge
  cases, and silent failures (principle 9). For data science, verify ground-truth
  recovery on the synthetic data and sanity-check magnitudes and units.
- **Style review:** check the change against every principle in the
  `delab-coding-practices` skill, and cite the principle number for each
  finding.

Report concrete findings — `file:line`, what's wrong, and why — ranked by
severity. Do not rubber-stamp; "looks fine" is not a review.
