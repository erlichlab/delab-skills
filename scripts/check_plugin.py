#!/usr/bin/env python3
"""Validate the plugin/marketplace layout of this repo.

Run with:  python3 scripts/check_plugin.py

Deliberate deviation from principle 1 (no pyproject/lockfile): this repo is
plain Markdown and JSON with no runtime dependencies, so the check uses only
the standard library and runs on a bare clone with no environment to create.

Every check takes the repo root as an argument and returns a list of problem
strings rather than printing or exiting, so each one is a pure function that
can be pointed at a synthetic fixture tree in a test (principle 2, 6).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Markdown inline links: [text](target). Reference-style links and bare URLs in
# angle brackets are not used in this repo.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# ${CLAUDE_PLUGIN_ROOT}/... paths that a command file tells the agent to read.
PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./<>-]+)")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def load_json(path: Path) -> tuple[dict | None, list[str]]:
    """Parse a JSON file, returning (data, problems). Never raises."""
    if not path.exists():
        return None, [f"{path}: missing"]
    try:
        return json.loads(path.read_text()), []
    except json.JSONDecodeError as exc:
        return None, [f"{path}: invalid JSON — {exc}"]


def frontmatter_field(path: Path, field: str) -> str | None:
    """Value of a top-level scalar frontmatter field, or None if absent/empty.

    Good enough for `name:`/`description:`; it handles YAML block scalars
    (`description: >-`) by treating any indented continuation as part of the
    value, which is the only multi-line form used here.
    """
    match = FRONTMATTER.match(path.read_text())
    if match is None:
        return None
    lines = match.group(1).splitlines()
    for i, line in enumerate(lines):
        if not line.startswith(f"{field}:"):
            continue
        value = line[len(field) + 1 :].strip().lstrip(">|-").strip()
        continuation = [
            rest.strip() for rest in lines[i + 1 :] if rest.startswith((" ", "\t"))
        ]
        return " ".join(filter(None, [value, *continuation])) or None
    return None


def slugify(heading: str) -> str:
    """GitHub's anchor slug for a Markdown heading line."""
    text = heading.lstrip("#").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text)


def anchors(path: Path) -> set[str]:
    return {
        slugify(line)
        for line in path.read_text().splitlines()
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
    # A skill with no description is never auto-loaded, which fails silently at
    # the only moment that matters — so treat it as an error, not a warning.
    problems += [
        f"{skill}: frontmatter has no `description`, so the skill will never load"
        for skill in skill_files
        if not frontmatter_field(skill, "description")
    ]
    problems += [
        f"{command}: frontmatter has no `description`"
        for command in sorted(plugin_dir.glob("commands/*.md"))
        if not frontmatter_field(command, "description")
    ]
    problems += check_plugin_root_refs(plugin_dir)
    return problems


def check_plugin_root_refs(plugin_dir: Path) -> list[str]:
    """Every ${CLAUDE_PLUGIN_ROOT}/... path a command reads actually exists.

    These are how the commands find SKILL.md; a stale one leaves the command
    silently working from no principles at all.
    """
    problems = []
    for command in sorted(plugin_dir.glob("commands/*.md")):
        for ref in PLUGIN_ROOT_REF.findall(command.read_text()):
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
        for target in LINK.findall(doc.read_text()):
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
