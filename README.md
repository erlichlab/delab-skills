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

The first line registers the `delab` marketplace from GitHub; the second installs
the `delab-coding-practices` plugin from it. Once installed, the skill loads
automatically when you're writing or reviewing lab code, and you get two
commands: `/delab-review` and `/delab-refactor` (below).

> Not on GitHub yet? You can also add a marketplace from a local clone:
> `/plugin marketplace add /path/to/delab-skills`.

### Commands

- **`/delab-review [path]`** — reviews the current diff (or a given path) against
  the principles and reports violations with the principle number and a fix.
- **`/delab-refactor <path>`** — rewrites the target code to follow the
  principles, explaining each change.

### Using the guidance outside Claude Code

Every file is plain Markdown, so other assistants can use it too — point Cursor /
Copilot at
[`SKILL.md`](plugins/delab-coding-practices/skills/delab-coding-practices/SKILL.md)
and the relevant `languages/*.md` as project rules or attached context.

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
│       ├── commands/                    # /delab-review, /delab-refactor
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
loader must find, a `description` in each `SKILL.md` frontmatter without which
the skill silently never loads, and Markdown links that must resolve. None of it
is exercised until someone runs `/plugin install` and nothing appears, so it's
checked instead:

```bash
python3 scripts/check_plugin.py
```

Standard library only — no environment to set up — and it runs in CI on every
push. Run it before opening a merge request.

## Status

Early — `v0.1`. All four language files (Python, Julia, MATLAB, R) are
fleshed out, and the repo is packaged as an installable plugin. Feedback and
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
