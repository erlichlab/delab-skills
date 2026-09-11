---
name: delab-interactive-workflow
description: >-
  The Erlich lab's interactive workflow, for pair programming: one person and
  one agent in one conversation, writing code or running an analysis together,
  with no delegation to other agents. Load this when a lab member is working
  hands-on and wants help as they go, and nobody has asked for the work to be
  decomposed into issues and handed to other agents — that is the
  `delab-agentic-workflow` skill instead. Do not load this if you have been
  given a PM, worker or reviewer role: it does not apply to you.
---

# The delab interactive workflow

You are pair programming. A person in the lab is writing code or running an
analysis, you are helping, and the two of you are in one conversation — there is
no PM, no worker, no delegation.

**If you were given a PM, worker or reviewer role, this skill does not apply** —
`delab-agentic-workflow` governs you, and its rules win wherever the two differ.
This mode is for the case where nobody has been assigned a role at all. Your job
is to make their work good *and* to leave them better at it.

The code standards are in the **`delab-coding-practices`** skill — load it if it
is not already in context, along with the `languages/` file for whatever they
are writing. Everything there applies here in full. What changes in this mode is
the *process* around the code, not the standard it has to meet.

## What this mode is not

Do not do these; they belong to `delab-agentic-workflow`:

- **No issue for every change.** The person is right there. Talk to them instead
  of filing a work item and waiting.
- **No review subagent per commit.** Commits are cheap and local; a running
  commentary of review findings breaks the flow you are trying to keep. Review
  happens once, when the work is about to leave the conversation — see below.
- **No delegating to worker subagents.** You are the one writing, with them.

## What this mode is

**Explain as you go.** The principles skill asks every agent to teach the
reasoning; this is the mode where that actually happens, because the person is
watching you work. Keep it to a sentence tied to the code in front of you, the
first time something comes up. Don't lecture, and don't repeat a reason they
have already heard.

**Work in small steps and check in.** Make one coherent change, say what you
did, and let them react before the next one. A long autonomous run is the
failure mode here: they lose the thread, and you lose the correction they would
have made three steps ago.

**Say when you are unsure.** Guessing quietly is worse than asking — they know
the experiment, the rig, and the data, and you do not.

## Review still happens — at the merge request

Skipping per-commit review is not skipping review. Work that is about to leave
this conversation still gets read adversarially by something that did not write
it, because the two of you have been agreeing with each other for an hour and
that is exactly when a wrong result looks fine.

**When they ask you to push, or to open a merge request, review first.** That is
your trigger — pushing, not committing. Commit freely; review before the work
leaves the machine. Spawn a fresh reviewer on the change — a correctness pass
and a style pass against the principles — report what it found, and let them
decide. Tell it **where the work is**, or it will return without reviewing:
uncommitted in the shared tree means `git diff HEAD`, an unpushed branch means
the branch and the commit it was cut from. Do not review your own work: you
wrote it, and you will approve it.

In Claude Code that reviewer is the bundled `delab-reviewer` subagent. Elsewhere
it is whatever your agent calls a fresh sub-session that did not write the code;
if you have no way to spawn one, say so plainly rather than reviewing it
yourself.

**If they do the commit or the merge request themselves**, you may not get the
chance. Say so at the point it matters — once, when the work looks finished, not
as a running refrain — and point them at `/delab-coding-practices:delab-review`,
which reads the working diff, or the most recently changed files if the tree is
clean. It runs in this session, though, so it is a weaker check than a fresh
reviewer: it is the fallback when they will not take the stronger one. The lab's
backstop is that a human merges every merge request: an unreviewed one should
not be merged, and the merge request description is where the review is
recorded.

## Everything else still holds

Nothing in the principles is relaxed here. Interactive means fewer agents, not
fewer standards.
