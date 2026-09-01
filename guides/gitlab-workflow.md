# GitLab workflow

The lab uses **GitLab** by default (a few projects live on GitHub; the flow is the
same). This guide is the practical companion to
[principle 12](../SKILL.md#12-work-in-short-lived-feature-specific-branches) —
*work in short-lived, feature-specific branches*.

## Keep branches short-lived

Branch per unit of work — one function, one plot, one analysis. Open a merge
request (MR) and merge to `main` (after review) as soon as that unit is done,
rather than continuing to develop on the same branch indefinitely.

Benefits:

- MR diff reflects the actual scope of the change (reviewable, honest history).
- Branch name stays meaningful (`feat/foo-123`, not `my-branch`).
- Low conflict risk — you're never far behind `main`.
- Nothing to "clean up" later — `main` already reflects finished, reviewed work.

## Enable: delete source branch on merge

Set **"delete source branch on merge"** as the project default (Settings → Merge
requests), so finishing an MR naturally closes out the branch too. Merged branches
don't linger, and the branch list stays an accurate picture of work in flight.

## Backstop: catch drifting branches early

Periodically flag branches that have commits ahead of `main` but **no MR history** —
these are the long-lived branches principle 12 warns about, and catching them early
beats discovering them at publication crunch time.

- `GET /projects/:id/repository/branches` — list branches (each entry reports
  whether it's ahead of the default branch).
- `GET /projects/:id/merge_requests?source_branch=X` — check whether branch `X`
  has ever had an MR.

A branch that is ahead of `main` and has zero MRs is drifting: open an MR for it,
or delete it if it's abandoned. This is a natural periodic task for the
project-manager agent (see the [agentic-coding guides](agentic-coding-for-agents.md)).

## The normal loop

```
git switch -c feat/short-name    # branch off an up-to-date main
# ... small, focused change; commit with a clear message (principle 10) ...
git push -u origin feat/short-name
# open an MR, get it reviewed, merge to main (source branch auto-deletes)
```

Merging into protected `main` stays a human/Maintainer action; branches, pushes,
and MRs can be opened by a Developer-role account (including a bot — see the
agentic guides for identity and token setup).
