# delab skills

Shared coding practices for the Erlich lab (delab), packaged as a **Claude Code
plugin** (a skill plus a couple of slash commands) that you install from a
marketplace. The goal is that research code across the lab — behavior/rig
control, ephys and imaging analysis, modeling, and statistics — comes out
**reproducible, readable, and fast enough**, and consistent from person to
person.

It's built around two goals:

1. Get your assistant to write code that follows lab practices by default.
2. Have it **explain *why*** as it goes, so you learn the reasoning and start
   choosing these practices on your own — not just following rules.

## Install as a plugin

In Claude Code, add this repo as a marketplace and install the plugin:

```
/plugin marketplace add erlichlab/delab-skills
/plugin install delab-coding-practices@delab
```

The first line registers the `delab` marketplace; the second installs the
`delab-coding-practices` plugin from it. Once installed, the skill loads
automatically when you're writing or reviewing lab code, and you get three
commands and two orchestration agents (below).

> **Where the repo lives.** Development happens on GitLab
> (`sainsbury-wellcome-centre/delab/delab-skills`); `erlichlab/delab-skills` on
> GitHub is a mirror, and it's what `/plugin marketplace add` fetches — Claude
> Code's `owner/repo` shorthand resolves to GitHub. Send merge requests to
> GitLab. You can also add a marketplace straight from a local clone:
> `/plugin marketplace add /path/to/delab-skills`.

### Commands

Plugin commands are namespaced by plugin, so these are the names that always
work. The bare `/delab-review` form also works as long as no other installed
plugin claims that name.

- **`/delab-coding-practices:delab-enforce-style [goal]`** — makes the main
  session act as the delab **project manager**: it adopts the principles and the
  agentic workflow, decomposing work into GitLab issues and delegating to the
  agents below (gating complex plans on your confirmation).
- **`/delab-coding-practices:delab-review [path]`** — reviews the current diff
  (or a given path) against the principles and reports violations with the
  principle number and a fix.
- **`/delab-coding-practices:delab-refactor <path>`** — rewrites the target code
  to follow the principles, explaining each change.

### Agents

The plugin ships two subagents with the principles **preloaded**, so the PM
delegates to them without hand-wiring the standards each time:

- **`delab-coder`** — implements one work item following the principles (TDD for
  infrastructure, synthetic-data-first for analysis pipelines).
- **`delab-reviewer`** — a fresh, **read-only**, adversarial reviewer that checks
  correctness and conformance to the principles, citing principle numbers.

### Using the guidance outside Claude Code

The skill follows the [Agent Skills](https://agentskills.io/specification) open
standard, so it isn't Claude-only. Codex, Gemini CLI, Cursor and Copilot all
discover skills from `.agents/skills/` — copy the skill directory there in your
project, or into `~/.agents/skills/` to have it everywhere:

```bash
git clone https://github.com/erlichlab/delab-skills.git   # mirror of the GitLab repo
mkdir -p ~/.agents/skills   # without this, cp silently names the skill "skills"
cp -r delab-skills/plugins/delab-coding-practices/skills/delab-coding-practices \
      ~/.agents/skills/
```

Copy the **whole directory**, not just `SKILL.md`: `languages/` and `guides/`
are loaded on demand. Each agent also has its own path (`.gemini/skills/`,
`.cursor/skills/`, `.github/skills/`) and its own precedence rules — see your
agent's docs if you need a per-project override. To update, `git pull` and copy
again; `cp -r` merges, so delete the destination first if you want files removed
upstream to disappear.

> **In Claude Code, use the plugin instead** — it does *not* read
> `.agents/skills/`. See [Install as a plugin](#install-as-a-plugin) above.

For an agent with no skill discovery, paste the raw files in as project rules or
attached context — `SKILL.md` plus the `languages/` file for the language you're
working in:

```
https://raw.githubusercontent.com/erlichlab/delab-skills/main/plugins/delab-coding-practices/skills/delab-coding-practices/SKILL.md
https://raw.githubusercontent.com/erlichlab/delab-skills/main/plugins/delab-coding-practices/skills/delab-coding-practices/languages/python.md
```

The PM / worker / reviewer workflow does not travel: `delab-coder` and
`delab-reviewer` are Claude Code subagents. Elsewhere it's text to read or paste
—
[`agentic-coding-for-agents.md`](plugins/delab-coding-practices/skills/delab-coding-practices/guides/agentic-coding-for-agents.md)
and
[`agentic-coding-for-humans.md`](plugins/delab-coding-practices/skills/delab-coding-practices/guides/agentic-coding-for-humans.md).

## What's inside

The plugin lives under `plugins/delab-coding-practices/`; the skill and its
supporting files are in
`plugins/delab-coding-practices/skills/delab-coding-practices/`:

- **`SKILL.md`** — the twelve core principles, stated language-agnostically:
  package/environment management, functional code, caching expensive results,
  `map`/vectorization over hand-rolled loops, small single-purpose functions,
  test-driven development, never storing secrets or hard-coded paths, keeping
  I/O, analysis, and plotting in separate layers, failing loudly, comments that
  explain the present rather than the history, optimizing only when needed
  (parallelizing at the coarsest level), and working in short-lived feature
  branches.
- **`languages/`** — per-language idioms and concrete *before → after*
  examples: `python.md`, `julia.md`, `matlab.md`, `r.md`.
- **`guides/`** — how to *work with LLM agents* in the lab:
  [`agentic-coding-for-humans.md`](plugins/delab-coding-practices/skills/delab-coding-practices/guides/agentic-coding-for-humans.md)
  (you as PI: set goals, approve complex plans, own correctness) and
  [`agentic-coding-for-agents.md`](plugins/delab-coding-practices/skills/delab-coding-practices/guides/agentic-coding-for-agents.md)
  (instructions for the project-manager / worker / reviewer roles). Plus
  [`gitlab-workflow.md`](plugins/delab-coding-practices/skills/delab-coding-practices/guides/gitlab-workflow.md)
  — the practical GitLab branch/MR workflow behind principle 12.

The assistant loads `SKILL.md` for the principles and the matching
`languages/<lang>.md` file when it knows which language you're working in. The
`guides/` describe the *workflow* around the agents — a PM agent decomposing work
into GitLab issues, delegating to worker subagents, and gating complex plans on
your confirmation.

## Repository layout

```
delab-skills/
├── .claude-plugin/
│   └── marketplace.json                 # the "delab" marketplace catalog
├── plugins/
│   └── delab-coding-practices/
│       ├── .claude-plugin/plugin.json   # plugin manifest
│       ├── commands/                    # delab-enforce-style, delab-review, delab-refactor
│       ├── agents/                      # delab-coder, delab-reviewer
│       └── skills/
│           └── delab-coding-practices/
│               ├── SKILL.md
│               ├── languages/
│               └── guides/
├── scripts/check_plugin.py              # validates the layout above
├── .gitlab-ci.yml                       # runs it on every push
├── LICENSE
└── README.md
```

### Checking the layout

The structure above is a contract — JSON that must parse, a `source` path the
loader must find, frontmatter that satisfies the [Agent Skills
spec](https://agentskills.io/specification) (a `name` matching the skill's
directory, a `description` within the 1024-character cap, and YAML an agent can
actually parse — without a description, or with broken YAML, a client skips the
skill and says nothing), and Markdown links that must resolve. None of it is exercised until someone runs `/plugin install` and
nothing appears, so it's checked instead:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'   # the checker's own tests
python3 scripts/check_plugin.py                          # this repo's tree
```

The checker only ever runs against a valid tree, so it cannot catch itself
wrongly accepting a bad one — that's what the tests are for. Standard library
only, no environment to set up, and both run in CI on every push. Run them
before opening a merge request.

## Status

Early — `v0.2`. All four language files (Python, Julia, MATLAB, R) are
fleshed out, the repo is packaged as an installable plugin, and the skill
follows the Agent Skills standard so it travels to other agents. Feedback and
contributions from the lab are welcome.

Planned for a later version: a section on scaling analyses to the cluster
(SLURM) — job arrays over sessions/subjects, resource requests, and how it
extends principle 11.

## Credits

Inspired in part by Tim Holy's
[`claude_config`](https://github.com/timholy/claude_config), which serves a
similar purpose for Julia scientific computing. Several ideas here — the
small, focused-rule format, the fail-fast stance, comments that explain the
present rather than the history, synthetic test fixtures, and much of the
Julia guidance — draw on that work.

## Contributing

Keep the principles language-agnostic in `SKILL.md`; put language-specific
tooling and examples in the `languages/` files. Every practice should come with
a short *before → after* pair and a one-line reason it matters. Run
`python3 scripts/check_plugin.py`, then work on a short-lived branch and open a
merge/pull request (principle 12).
