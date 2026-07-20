# delab skills

Shared coding practices for the Erlich lab (delab), packaged as a **skill** you
can install into your LLM coding assistant. The goal is that research code
across the lab — behavior/rig control, ephys and imaging analysis, modeling,
and statistics — comes out **reproducible, readable, and fast enough**, and
consistent from person to person.

It's built around two goals:

1. Get your assistant to write code that follows lab practices by default.
2. Have it **explain *why*** as it goes, so you learn the reasoning and start
   choosing these practices on your own — not just following rules.

## What's inside

- **`SKILL.md`** — the ten core principles, stated language-agnostically:
  package/environment management, functional code, caching expensive results,
  `map`/vectorization over hand-rolled loops, small single-purpose functions,
  test-driven development, never storing secrets or hard-coded paths, keeping
  I/O, analysis, and plotting in separate layers, failing loudly, and comments
  that explain the present rather than the history.
- **`languages/`** — per-language idioms and concrete *before → after*
  examples: `python.md`, `julia.md`, `matlab.md`, `r.md`.

The assistant loads `SKILL.md` for the principles and the matching
`languages/<lang>.md` file when it knows which language you're working in.

## Installing

Clone the repo somewhere stable:

```bash
git clone https://gitlab.com/sainsbury-wellcome-centre/delab/delab-skills.git
```

Then point your assistant at it:

- **Claude Code / agents that support Skills** — place (or symlink) this folder
  in your skills directory so `SKILL.md` is discovered.
- **Cursor / Copilot / other assistants** — add `SKILL.md` (and the relevant
  `languages/*.md`) to your project rules or attach them as context.

Any tool that can read Markdown context can use these files; the `SKILL.md`
frontmatter is what Skill-aware tools use to load it automatically.

## Status

Early — `v0.1`. Python, Julia, and MATLAB are fleshed out; R is next.
Feedback and contributions from the lab are welcome.

## Credits

Inspired in part by Tim Holy's
[`claude_config`](https://github.com/timholy/claude_config), which serves a
similar purpose for Julia scientific computing. Several ideas here — the
small, focused-rule format, the fail-fast stance, comments that explain the
present rather than the history, synthetic test fixtures, and much of the
forthcoming Julia guidance — draw on that work.

## Contributing

Keep the principles language-agnostic in `SKILL.md`; put language-specific
tooling and examples in the `languages/` files. Every practice should come with
a short *before → after* pair and a one-line reason it matters. Open a merge
request against `main`.
