#!/usr/bin/env python3
"""Validate the plugin/marketplace layout of this repo.

Run with:  python3 scripts/check_plugin.py

Deliberate deviation from principle 1 (no pyproject/lockfile): this repo is
plain Markdown and JSON with no runtime dependencies, so the check uses only
the standard library and runs on a bare clone with no environment to create.

Checks return a list of problem strings rather than printing or exiting, so
they can be called from a test on a synthetic input (principle 2, 6). The
frontmatter checks take parsed values rather than a path, so they need no
filesystem at all. Tests are in scripts/test_check_plugin.py; the checks that
walk the repo layout are still covered only by running against this repo.
"""

from __future__ import annotations

import json
import re
import sys
from itertools import takewhile
from pathlib import Path

# Markdown inline links: [text](target). Reference-style links and bare URLs in
# angle brackets are not used in this repo.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# ${CLAUDE_PLUGIN_ROOT}/... paths that a command file tells the agent to read.
PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./<>-]+)")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
# A top-level frontmatter key and whatever follows the colon on the same line.
# Unindented only, so nothing inside a block scalar or a list can match.
FRONTMATTER_KEY = re.compile(r"\A([A-Za-z0-9_-]+):(.*)\Z")
# A YAML block-scalar indicator introducing a multi-line value: `>`, `|`, `>-`,
# `|+`. The value itself is on the following indented lines. The rarer forms
# that put the indentation indicator first (`|2-`) are not matched, and neither
# is a trailing comment; both would leak the header into the parsed value.
BLOCK_SCALAR = re.compile(r"\A[>|][+-]?\d*\Z")
# Agent Skills spec: 1-64 characters, lowercase alphanumerics separated by
# single hyphens. https://agentskills.io/specification
SKILL_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SKILL_NAME_MAX = 64
SKILL_DESCRIPTION_MAX = 1024


def load_json(path: Path) -> tuple[dict | None, list[str]]:
    """Parse a JSON file, returning (data, problems). Never raises."""
    if not path.exists():
        return None, [f"{path}: missing"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"{path}: invalid JSON — {exc}"]


def parse_frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar fields of a YAML frontmatter block.

    Scalars only — a list value (`tools:`) is returned joined and is not
    meaningful. Handles plain scalars, quoted scalars, and block scalars
    (`description: >-`), whose value is the run of indented lines that follows.
    A blank line is part of that run: it is the paragraph break inside a folded
    scalar, so stopping at it would silently truncate the value.
    """
    match = FRONTMATTER.match(text)
    if match is None:
        return {}
    lines = match.group(1).splitlines()
    fields = {}
    for i, line in enumerate(lines):
        key_match = FRONTMATTER_KEY.match(line)
        if key_match is None:
            continue
        key, inline = key_match.group(1), key_match.group(2).strip()
        block = takewhile(
            lambda rest: not rest.strip() or rest.startswith((" ", "\t")),
            lines[i + 1 :],
        )
        folded = BLOCK_SCALAR.match(inline)
        parts = [] if folded else [inline]
        parts += [rest.strip() for rest in block]
        value = " ".join(part for part in parts if part)
        # Quotes inside a block scalar are literal text, not YAML quoting.
        fields[key] = value if folded else unquote(value)
    return fields


def unquote(value: str) -> str:
    """Strip the surrounding quotes from a quoted plain YAML scalar."""
    for quote in ('"', "'"):
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    return value


def frontmatter_field(path: Path, field: str) -> str | None:
    """Value of a top-level scalar frontmatter field, or None if absent/empty."""
    return parse_frontmatter(path.read_text(encoding="utf-8")).get(field) or None


def slugify(heading: str) -> str:
    """GitHub's anchor slug for a Markdown heading line."""
    text = heading.lstrip("#").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text)


def anchors(path: Path) -> set[str]:
    return {
        slugify(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


def check_marketplace(root: Path) -> list[str]:
    """The marketplace catalog parses and every plugin it lists exists."""
    data, problems = load_json(root / ".claude-plugin" / "marketplace.json")
    if data is None:
        return problems
    if not data.get("name"):
        problems.append("marketplace.json: missing `name`")
    plugins = data.get("plugins")
    if not plugins:
        return problems + ["marketplace.json: no plugins listed"]

    for entry in plugins:
        name, source = entry.get("name"), entry.get("source")
        if not name or not source:
            problems.append(f"marketplace.json: entry needs `name` and `source`: {entry}")
            continue
        plugin_dir = (root / source).resolve()
        if not plugin_dir.is_dir():
            problems.append(f"marketplace.json: `source` {source} is not a directory")
            continue
        if plugin_dir.name != name:
            problems.append(
                f"marketplace.json: plugin `{name}` lives in {plugin_dir.name}/ — "
                "directory name and plugin name must match"
            )
        problems += check_plugin(plugin_dir, name)
    return problems


def check_plugin(plugin_dir: Path, expected_name: str) -> list[str]:
    """The plugin manifest agrees with the catalog and its skills are loadable."""
    manifest, problems = load_json(plugin_dir / ".claude-plugin" / "plugin.json")
    if manifest is None:
        return problems
    if manifest.get("name") != expected_name:
        problems.append(
            f"{plugin_dir}/.claude-plugin/plugin.json: name is "
            f"{manifest.get('name')!r}, marketplace says {expected_name!r}"
        )
    if not manifest.get("description"):
        problems.append(f"{plugin_dir}: plugin.json has no `description`")

    skills_dir = plugin_dir / manifest.get("skills", "./skills")
    if not skills_dir.is_dir():
        return problems + [f"{plugin_dir}: skills dir {skills_dir} does not exist"]

    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        problems.append(f"{skills_dir}: contains no <skill>/SKILL.md")
    for skill in skill_files:
        problems += check_skill_frontmatter(skill)
    problems += [
        f"{entry}: frontmatter has no `description`"
        for pattern in ("commands/*.md", "agents/*.md")
        for entry in sorted(plugin_dir.glob(pattern))
        if not frontmatter_field(entry, "description")
    ]
    problems += check_manifest_paths(plugin_dir, manifest)
    problems += check_plugin_root_refs(plugin_dir)
    return problems


def check_frontmatter_yaml(text: str) -> list[str]:
    """Frontmatter breakages that make a client skip the skill silently.

    A client that cannot parse the YAML drops the skill and logs the error
    somewhere the author never looks, so these have to be caught here. Only the
    two breakages that actually occur are checked; this is not a YAML validator.
    """
    match = FRONTMATTER.match(text)
    if match is None:
        return []
    lines = match.group(1).splitlines()
    problems = []
    if any(line.startswith("\t") for line in lines):
        problems.append(
            "frontmatter is indented with tabs somewhere; YAML forbids tabs "
            "for indentation and the skill will not parse"
        )
    for line in lines:
        key_match = FRONTMATTER_KEY.match(line)
        if key_match is None:
            continue
        value = key_match.group(2).strip()
        if value[:1] in ('"', "'") or BLOCK_SCALAR.match(value):
            continue
        if ": " in value:
            problems.append(
                f"`{key_match.group(1)}` has an unquoted colon in {value!r}; "
                "YAML reads it as a nested key — quote the value or use `>-`"
            )
    return problems


def check_skill_frontmatter(skill: Path) -> list[str]:
    """A skill's frontmatter satisfies the Agent Skills spec, not just Claude Code.

    Claude Code infers a skill's name from its directory, so it loads a skill
    whose frontmatter has no `name` at all. Clients are advised to be lenient
    about the name and to skip a skill outright only when the description is
    missing or the YAML will not parse — so the name checks keep us honest
    against the spec, and the description and YAML checks are the ones that
    decide whether the skill loads elsewhere.
    """
    text = skill.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    if not fields:
        return [f"{skill}: no parseable YAML frontmatter, so no agent will load it"]
    problems = check_frontmatter_yaml(text)
    problems += check_skill_name(fields.get("name"), skill.parent.name)
    problems += check_skill_description(fields.get("description"))
    return [f"{skill}: {problem}" for problem in problems]


def check_skill_name(name: str | None, directory: str) -> list[str]:
    """The `name` field is present, well-formed, and matches the directory."""
    if name is None:
        return [
            "frontmatter has no `name`; Claude Code infers it from the directory, "
            "but the Agent Skills spec requires it and other agents reject the "
            "skill without it"
        ]
    if not name:
        return ["`name` is empty"]
    problems = []
    if not SKILL_NAME.match(name):
        problems.append(
            f"`name` is {name!r}; the spec allows only lowercase letters and "
            "digits separated by single hyphens — no uppercase, and no leading, "
            "trailing or doubled hyphens"
        )
    if len(name) > SKILL_NAME_MAX:
        problems.append(
            f"`name` is {len(name)} characters; the spec caps it at {SKILL_NAME_MAX}"
        )
    if name != directory:
        problems.append(
            f"`name` is {name!r} but the directory is {directory!r}; "
            "the spec requires them to match"
        )
    return problems


def check_skill_description(description: str | None) -> list[str]:
    """The `description` field is present and within the spec's length cap.

    A skill with no description is never auto-loaded, which fails silently at
    the only moment that matters — so treat it as an error, not a warning.
    """
    if not description:
        return ["frontmatter has no `description`, so the skill will never load"]
    if len(description) > SKILL_DESCRIPTION_MAX:
        return [
            f"`description` is {len(description)} characters; "
            f"the spec caps it at {SKILL_DESCRIPTION_MAX}"
        ]
    return []


def check_manifest_paths(plugin_dir: Path, manifest: dict) -> list[str]:
    """`commands` and `agents` in the manifest point at things the loader accepts.

    Both fields replace the default directory rather than adding to it, and the
    loader takes only Markdown files there — `agents` rejects a directory
    outright ("Invalid string: must end with .md") and refuses to install the
    plugin. Since `commands/` and `agents/` are scanned by default, the fix for
    a directory value is almost always to drop the field.
    """
    problems = []
    for field in ("commands", "agents"):
        value = manifest.get(field)
        if value is None:
            continue
        entries = [value] if isinstance(value, str) else value
        for entry in entries:
            target = plugin_dir / entry
            if not str(entry).endswith(".md"):
                kind = "a directory" if target.is_dir() else "not a Markdown file"
                problems.append(
                    f"{plugin_dir}: plugin.json `{field}` lists {entry} — {kind}; "
                    f"list individual .md files, or drop `{field}` to use the "
                    f"default {field}/ directory"
                )
            elif not target.is_file():
                problems.append(
                    f"{plugin_dir}: plugin.json `{field}` lists {entry}, "
                    "which does not exist"
                )
    return problems


def check_plugin_root_refs(plugin_dir: Path) -> list[str]:
    """Every ${CLAUDE_PLUGIN_ROOT}/... path a command reads actually exists.

    These are how the commands find SKILL.md; a stale one leaves the command
    silently working from no principles at all.
    """
    problems = []
    for command in sorted(plugin_dir.glob("commands/*.md")):
        for ref in PLUGIN_ROOT_REF.findall(command.read_text(encoding="utf-8")):
            # `languages/<lang>.md` is a placeholder the agent fills in.
            target = plugin_dir / ref
            if "<" in ref:
                target = target.parent
            if not target.exists():
                problems.append(f"{command}: ${{CLAUDE_PLUGIN_ROOT}}/{ref} does not exist")
    return problems


def check_links(root: Path) -> list[str]:
    """Every relative Markdown link — and heading anchor — resolves."""
    problems = []
    for doc in sorted(root.rglob("*.md")):
        if ".git" in doc.parts:
            continue
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            destination = (doc.parent / path_part).resolve() if path_part else doc
            if not destination.exists():
                problems.append(f"{doc.relative_to(root)}: dead link → {target}")
            elif anchor and anchor not in anchors(destination):
                problems.append(f"{doc.relative_to(root)}: dead anchor → {target}")
    return problems


def main(root: Path) -> int:
    problems = [
        # Report paths relative to the repo so the message is the same whether
        # it comes from a laptop or a CI runner's checkout directory.
        problem.replace(f"{root}/", "")
        for check in (check_marketplace, check_links)
        for problem in check(root)
    ]
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} problem(s) found.", file=sys.stderr)
        return 1
    print("OK: marketplace, plugin manifest, skills, commands and links all check out.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent))
