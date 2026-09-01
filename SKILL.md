---
name: delab-coding-practices
description: >-
  Coding standards for the Erlich lab (delab). Load this whenever you are
  writing, reviewing, or refactoring research code in Python, Julia, MATLAB,
  or R — behavior/rig control, ephys and imaging analysis, modeling, or
  statistics. Enforces reproducible environments, functional and testable
  code, cached computation, vectorization, small functions, and keeping
  secrets and hard-coded paths out of the repository. When the user is working
  in a specific language, also read the matching file in `languages/`.
---

# delab coding practices

Guidance for writing research code that is **reproducible, readable, and fast
enough** — consistent across everyone in the lab. The goal is code a labmate
(or you, in six months) can run and trust without a phone call.

**Two goals, not one:**

1. **Write code that follows these practices** by default.
2. **Teach the person you're helping *why*.** Most people using this skill are
   students learning to write research code. Don't just silently apply a
   principle — briefly explain the advantage the first time it comes up
   ("I'm caching this to disk so re-running the notebook takes seconds instead
   of re-doing the 20-minute feature extraction"). The aim is that they
   internalize the reasoning and choose these practices on their own, not that
   they follow a rule they don't understand. Keep explanations short and tied
   to the concrete code at hand; don't lecture.

Each principle below is stated language-agnostically. Concrete *before → after*
examples live in the per-language files; when you know the language, read it:

- Python  → `languages/python.md`
- Julia   → `languages/julia.md`
- MATLAB  → `languages/matlab.md`
- R       → `languages/r.md`

Apply these by default. They are strong defaults, not laws — if a principle
genuinely doesn't fit, say why in a comment rather than silently ignoring it.

---

## 1. Package & environment management

Every project declares its dependencies in a manifest that lives in the repo,
and pins them so an install is reproducible on another machine. Never rely on
"whatever is installed globally."

- One project = one isolated environment (not your base/system install).
- Commit the manifest **and** the lockfile.
- A fresh clone + one install command must reproduce a working environment.
- Per language: Python → `uv` + `pyproject.toml`; Julia → `Project.toml` +
  `Manifest.toml`; R → `renv`; MATLAB → a `.prj` project + a documented
  toolbox list.

## 2. Functional code

Prefer **pure functions**: output depends only on inputs, no hidden reads or
writes of global state, no surprise side effects.

- Pass data in as arguments and return results; don't reach out to globals.
- Separate *computation* (pure, testable) from *I/O and plotting* (the edges);
  principle 8 spells this out as three concrete layers.
- A function that both loads a file, computes, mutates a global, and plots is
  four functions wearing a trench coat.

## 3. Cache expensive local results

If a computation is slow and its inputs haven't changed, don't recompute it —
cache the result to disk, keyed on the inputs, and reuse it.

- Cache key = a hash of the inputs (and code version if relevant), so stale
  caches invalidate automatically.
- Caches are disposable: deleting the cache directory must only cost time, and
  the cache dir is git-ignored.
- This is what lets analysis notebooks re-run in seconds instead of hours.

## 4. Map / vectorize instead of hand-rolled loops

Prefer a `map`, comprehension, or vectorized array operation over a manual
index loop that pre-allocates and fills.

- **Often the win is clarity, not speed.** Factor the loop body into a small,
  named function and map over it: `map(fit_subject, subjids)`. Even when there's
  no speedup at all — e.g. fitting one model per subject — this is shorter, has
  no index bookkeeping to get wrong, reads as *what* it does, and lets you test
  `fit_subject` on its own. It naturally pushes you toward small functions
  (principle 5).
- **For numeric array work it's *also* much faster.** A vectorized operation
  replaces a Python-level loop with a compiled one.
- "For each x, compute f(x)" → `map(f, xs)` / `[f(x) for x in xs]` / vectorized.
- Reserve explicit loops for genuine sequential state (running accumulators,
  early exit, side-effecting I/O).

## 5. Small, single-purpose functions

A function should do one thing, be nameable in a short verb phrase, and fit on
a screen. If you need "and" to describe it, split it.

- Small functions are testable, reusable, and self-documenting.
- Deep nesting or a 200-line function is a refactor waiting to happen.

## 6. Test-driven development

Write a test that captures the intended behavior, watch it fail, then write the
code that makes it pass. Tests describe *what the code should do* and let you
refactor without fear.

- Test behavior and edge cases, not implementation details.
- Every bug fixed gets a regression test that would have caught it.
- Tests run with one command and (ideally) in CI on every push.
- **Corollary — use synthetic fixtures, not real data files.** A test builds its
  own tiny inputs, so a fresh clone with no lab data present still passes. This
  keeps tests portable and fast, and dovetails with principle 7 (no hard-coded
  data paths).

## 7. Never store secrets or credentials in code

No passwords, API keys, tokens, or connection strings in source — ever, not
even "temporarily." Once committed, assume it's compromised.

- Read secrets from environment variables or a config file that is git-ignored.
- Provide a committed `.env.example` / template showing the *names*, not values.
- The same applies to hard-coded absolute data paths — make roots configurable,
  don't bake `/Users/yourname/...` into the analysis.
- Keep generated cruft out of the repo: caches, build artifacts, and editor or
  session files belong in `.gitignore`. For OS junk that shows up in *every* repo
  — `.DS_Store`, editor swap files — set a **global** gitignore once so you never
  fight it per-project: `git config --global core.excludesfile ~/.gitignore_global`.

## 8. Separate I/O, analysis, and plotting

Three layers, three functions: **load** the data, **compute** on it, **draw**
it. Keep them apart.

- **I/O** — loads and saves data (files, caches, databases). Knows about paths
  and formats; hands back plain in-memory data. Pair it with caching (principle
  3): try the cache, and only compute-and-save on a miss.
- **Analysis** — pure computation on that in-memory data. No file access, no
  plotting. This is the layer you unit-test.
- **Plotting** — takes results (or calls the analysis) and draws. It accepts an
  existing axis/handle to draw into and creates its own figure *only* if none is
  given, so any single plot drops into a multi-panel figure unchanged.

This is the concrete, three-layer form of functional code (principle 2). The
payoff: you can test analysis without a disk or a display, swap a cache for a
database without touching analysis, and reuse a one-panel plot inside a larger
figure.

## 9. Fail loudly

When something unexpected happens, stop and surface it — don't paper over it with
a silent default, a bare catch-all, or a `NaN` that quietly propagates. A loud
failure at the source is a five-minute fix; a silent one becomes a wrong figure
you trust for a month.

- Validate inputs at the boundary and raise with a clear message (this is part
  of what pydantic buys you — principle 7).
- Never swallow an exception you didn't expect and can't handle.
- A fallback value is acceptable only when it's a *deliberate, documented*
  choice — say why in a comment (principle 10).

## 10. Comments explain the present, not the history

A comment explains the code that is there *now* — an invariant it must keep, or a
non-obvious reason it has to be this way. It is not a changelog.

- ✅ *why it must be this way*: "clip to ≥0; negative rates are a sensor glitch."
- ❌ *history / process*: "changed from mean to median", "as planned in the design
  doc", "was broken before, now fixed".
- Drop references to planning docs, tickets (beyond a terse issue link), or
  session notes — the reader may have none of that context.
- Match the surrounding code's comment density and style.
- **Corollary:** the same applies to commit messages — say what the change does
  and why, understandable to someone without the back-story.

## 11. Optimize only when needed — and parallelize at the coarsest level

Write for correctness and clarity first. Most code is fast enough; don't trade
readability for speed you don't need.

- **Measure before optimizing.** Profile to find the actual bottleneck instead of
  guessing — the slow line is rarely where you'd bet. Often the real fix is
  caching (principle 3) or vectorizing (principle 4), not hand-tuning, and those
  come first.
- **When you do need speed, parallelize at the highest level.** Most lab code is
  *embarrassingly parallel* over sessions, subjects, or animals — independent
  units with no shared state. Parallelize over those, not over inner iterations.
- **Coarse beats fine.** Parallelizing over *trials* is bad: thousands of tiny
  tasks whose per-task overhead — spawning workers, copying data to them —
  dwarfs the work. Over *sessions* it's good: each worker does substantial work
  and loads its own data once. A pure per-session analysis function (principle 8)
  is exactly the unit to map and then parallelize.
- **Threads or processes?** Shared-memory threads have low overhead but stay on
  one machine; separate processes isolate state and can scale across machines.
  The right pick is language-specific (and Python's GIL rules out threads for
  CPU-bound work) — see your language file.
- Scaling past one machine (a cluster / SLURM) is the same idea one level up —
  covered in a later version.

## 12. Work in short-lived, feature-specific branches

Do your work on a branch named for one feature or fix, keep it small, and merge it
into `main` through a merge request. Don't let a branch live for weeks or collect
unrelated changes.

- **One branch, one purpose.** Name it for what it does (`add-r-language`,
  `fix-cache-key`), not `wip` or `my-branch`.
- **Keep `main` working.** `main` should always be in a runnable state; do
  exploratory or half-finished work on a branch, never directly on `main`.
- **Short-lived beats long-lived.** A small branch is easy to review and rarely
  conflicts; a branch that drifts for weeks becomes a merge headache — merge early
  and often.
- **Open a merge request** so changes are reviewed before they land, and **delete
  the branch** once it's merged.
- The lab uses **GitLab** by default (a few projects live on GitHub); the flow is
  the same — branch, push, open a merge/pull request, merge to `main`.

Commit messages follow principle 10 (explain the present, not the history), and
`.gitignore` keeps generated cruft out of the repo (principle 7). For the
practical GitLab setup — deleting merged branches automatically, and a backstop
for catching drifting branches — see `guides/gitlab-workflow.md`.

---

## Using this skill

When asked to write or refactor lab code:

1. Read this file for the principles.
2. Read the matching `languages/<lang>.md` for idioms and the exact tooling.
3. Produce code that already follows these defaults — don't write the "before"
   version and wait to be corrected.
4. Explain the *why* as you go, so the person learns the advantage rather than
   just receiving a rule (see "Two goals" above).
