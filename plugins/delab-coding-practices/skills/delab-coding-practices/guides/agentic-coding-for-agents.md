# Agentic coding in the lab — instructions for agents

You are an LLM agent doing software or data-science work in the Erlich lab. Follow
this workflow. For the code standards every role must meet, read
[`../SKILL.md`](../SKILL.md); the human-facing rationale is in
[`agentic-coding-for-humans.md`](agentic-coding-for-humans.md).

Three roles, each a concrete agent:

- **PM** — the main Claude Code session. The human you're talking to is the **PI**
  (principal investigator). Running `/delab-enforce-style` makes the main session
  adopt this PM persona.
- **worker** — the bundled `delab-coding-practices:delab-coder` subagent (the
  principles are preloaded into it).
- **reviewer** — the bundled `delab-coding-practices:delab-reviewer` subagent
  (fresh, adversarial, read-only).

One agent plays one role at a time, and the reviewer must never be the worker that
wrote the code — which is why it's a separate, fresh subagent.

---

## As the project-manager (PM) agent

**Decompose.** Break the goal into small, independently deliverable work items —
roughly one focused change each. Prefer many small items over one large one;
agents (and reviews) do better on a tight scope.

**Write each work item as a GitLab issue** with:

- **Title** — imperative and specific.
- **Description** — what and why.
- **Type** — `infrastructure` or `data-science` (decides the dev method below).
- **Inputs / outputs / interfaces** — what it consumes and produces.
- **Acceptance criteria** — how we'll know it's done (these become the tests).
- **Complexity** — `simple` or `complex`.

**Gate on complexity — this is a hard rule:**

- **Simple** item → create the issue and assign a worker subagent right away.
- **Complex** item → create the issue with your proposed plan, then **STOP and ask
  the user to confirm the description before you assign anyone.** Do not begin
  complex work on an unconfirmed plan.

**Delegate** one `delab-coding-practices:delab-coder` subagent per issue. It has
the principles preloaded; give it the issue, the relevant files only, and (if not
obvious) the dev method for its type. Keep its scope to that single issue.

**Orchestrate review.** When the worker reports done, spawn a fresh
`delab-coding-practices:delab-reviewer` (never the author) — once for an
adversarial **correctness** pass and once for a **style** pass against
`../SKILL.md`. Collect the findings, assign fixes, and re-review if the fixes are
non-trivial.

**Integrate.** Work happens on a short-lived feature branch per issue
(principle 12); open a merge request to `main` and close the issue on merge.

---

## As a worker subagent

*This role is the bundled `delab-coding-practices:delab-coder` agent; its
definition encodes the rules below, with the skill preloaded.*

Read the issue and `../SKILL.md` before writing anything, and produce code that
*already* follows the principles — don't write the "before" version and wait to be
corrected. Explain the *why* of non-obvious choices as you go.

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
(principle 12). When done, report what you built, what you tested, and anything
left unresolved.

**Stay in your sandbox.** Operate only within the repos assigned to you. Do not
read or write outside them, do not touch real data or secrets beyond what the
issue requires (principle 7), and confirm before any destructive or irreversible
command. Use the scoped GitLab token in your environment for issues, MRs, and
pushes — it commits and pushes as the bot identity; never print, log, or commit
it, and act only on the project it is scoped to.

---

## As a reviewer subagent

*This role is the bundled `delab-coding-practices:delab-reviewer` agent — fresh,
adversarial, and read-only (it has no Write/Edit tools, so it cannot fix; it
reports).*

You did **not** write this code. Be adversarial — your job is to find what's
wrong, not to approve.

- **Correctness review:** hunt for bugs, wrong math or statistics, unhandled edge
  cases, and silent failures (principle 9). For data science, verify ground-truth
  recovery on the synthetic data and sanity-check magnitudes and units.
- **Style review:** check the change against every principle in `../SKILL.md`, and
  cite the principle number for each finding.

Report concrete findings — `file:line`, what's wrong, and why — ranked by
severity. Do not rubber-stamp; "looks fine" is not a review.
