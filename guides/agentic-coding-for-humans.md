# Agentic coding in the lab — a guide for humans

How to *drive* LLM coding agents to produce good lab code. This is the
human-facing companion to [`agentic-coding-for-agents.md`](agentic-coding-for-agents.md),
which is written for the agents themselves. For *what good code looks like*, see
[`../SKILL.md`](../SKILL.md) — the agents apply it; you make sure they did.

## The mental model: you're the PI, not the coder

You direct a small team of agents rather than writing every line:

- A **project-manager (PM) agent** breaks your goal into small work items,
  writes each as an issue, and delegates it.
- **Worker subagents** each implement one work item.
- **Reviewer subagents** — fresh, adversarial — check the result before it lands.

Your job is to set direction, approve the plan for anything non-trivial, and own
the final correctness. Most of your leverage is in *what* gets built and *whether
it's right*, not in typing.

## The loop

```
your goal
   │
   ▼
PM decomposes into small work items, each written as a GitLab issue
   │
   ├─ simple item  ──────────────► PM assigns a worker subagent
   │
   └─ complex item ─► YOU confirm the issue description ─► PM assigns a worker
                                                                │
                                                                ▼
                              worker implements on a feature branch
                              (infra → TDD;  data science → synthetic-data-first)
                                                                │
                                                                ▼
                        fresh reviewer subagents (NOT the author):
                          • adversarial correctness review
                          • style review against ../SKILL.md
                                                                │
                                                                ▼
                              fix findings → merge request → main → close issue
```

## Your responsibilities

1. **Set a clear goal and constraints.** What's the deliverable, what data, what
   must not change.
2. **Approve the plan for complex work.** The PM writes each work item as an issue;
   for anything complex it should stop and wait for you to confirm the issue
   *before* assigning it. This is your highest-leverage moment — fixing a wrong
   plan here costs a sentence; fixing it after implementation costs hours. Let
   simple, well-scoped items run without you.
3. **Own correctness.** Reviewers help, but a plausible-looking analysis can still
   be wrong — sign off yourself on anything headed for a paper, and verify by
   *running* it, not just reading the diff.

## Why issue-driven development

Each work item becomes a durable issue (the lab uses GitLab — principle 12). This
isn't bureaucracy:

- The issue is a **shared spec** — you, the worker, and the reviewers all work
  from the same description.
- For complex work, the issue **is the plan you approve** before anyone codes.
- Issues are **traceable** — every branch and merge request ties back to one, so
  it's clear why each change exists.

Keep work items **small and independently deliverable** — this is principle 5
(small functions) one level up. Small items are easier to specify, review, and
parallelize, and agents do markedly better on a tight scope than on a sprawling
one.

## Reviews are adversarial and separate

Never let the agent that wrote the code be the one that approves it — same
confirmation bias as a person marking their own homework. Require **two fresh
reviewer subagents**:

- **Correctness** — actively tries to break it: wrong results, edge cases, silent
  failures (principle 9). For analyses, that it recovers the known answer on
  synthetic data (below) and that magnitudes and units are sane.
- **Style** — conformance to every principle in `../SKILL.md`.

## Infrastructure vs data science

The development method depends on what you're building:

- **Infrastructure** (tools, plumbing, pipelines' scaffolding) → **standard TDD**:
  write a failing test for the acceptance criteria, then implement (principle 6).
- **Data science** (an analysis pipeline) → **synthetic data first**. Generate
  data with a *known ground truth*, write a test that the pipeline recovers it,
  then build the analysis until it does — **test-driven data science**. Real data
  has no answer key, so on real data you can't tell a bug from a discovery;
  synthetic data *is* your answer key. (This is the analysis-scale version of the
  synthetic-fixtures corollary under principle 6.)

## Sandbox the agent

Give the agent access to the repos it needs and nothing else. An agent that can
read your whole home directory can leak data or credentials; one that can write
anywhere can do real damage from a single bad command.

- **Simple, effective technique:** run the agent as a **dedicated, unprivileged
  Linux user** whose home contains only the repos you cloned for it — no access
  to your own files, data, or keys.
- Containers or VMs give stronger isolation if you want it. Lighter tools like
  `bubblewrap`/`firejail` exist but the lab hasn't vetted them — treat them as
  options to evaluate, not a recommendation.
- Regardless of sandbox: keep real data and secrets out of the agent's reach
  (principle 7), and confirm before anything destructive or irreversible.

## Common pitfalls

- **Rubber-stamping plans.** If you approve complex issues without reading them,
  you've given up your highest-leverage check.
- **Tasks too big or too vague.** Decompose; a sprawling prompt produces sprawling,
  hard-to-review output.
- **Trusting output you didn't run.** Especially plots and statistics.
- **Skipping synthetic-data tests** on an analysis — then you have no answer key.
- **One agent writing and reviewing** its own work.
- **Long-lived branches** that drift from `main` (principle 12).

## Tooling notes

- **Issues / branches / MRs:** GitLab by default (principle 12).
- **Agents:** in Claude Code, the PM spawns worker and reviewer subagents; give
  each the issue, a pointer to `../SKILL.md`, and only the files it needs.
- **Model & cost:** use a stronger model for planning/review and a cheaper one for
  mechanical work; watch token spend on large fan-outs.
