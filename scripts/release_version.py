#!/usr/bin/env python3
"""Version/tag logic for .github/workflows/release.yml.

The workflow needs two decisions on every push to `main` (including the ones
the GitLab -> GitHub mirror cron job makes): what tag this version of the
plugin should have, and whether that tag already exists — the second is what
makes an unbumped push a silent no-op instead of a duplicate-tag failure.
Both are plain string/JSON logic with no GitHub API involved, so they live
here as pure, tested functions rather than inline shell in the YAML.

What this script cannot cover, and why: the actual `gh release create` call,
GITHUB_TOKEN permissions, and the mirror push that triggers the workflow all
require a real GitHub repo and Actions run — there is no local stand-in for
them. Those were checked by careful manual review of the workflow YAML (and,
where the mirror allows, by an actual push), not by a test in this repo. See
scripts/test_release_version.py for what IS covered, and the report for how
the rest was verified.

Run the tests with:  python3 -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_PLUGIN_JSON = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "delab-coding-practices"
    / ".claude-plugin"
    / "plugin.json"
)


def read_version(plugin_json: Path) -> str:
    """The `version` field plugin.json declares.

    Raises if it's missing or empty rather than defaulting to something like
    "0.0.0" — a silent default here would tag and release under the wrong
    version instead of failing where the actual problem is (principle 9).
    """
    manifest = json.loads(plugin_json.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not version:
        raise ValueError(f"{plugin_json}: no `version` field")
    return version


def tag_for_version(version: str) -> str:
    """The git tag a plugin version is released under, e.g. `2.0.0` -> `v2.0.0`."""
    return f"v{version}"


def tag_exists(tag: str, existing_tags: list[str]) -> bool:
    """Whether `tag` is already among `existing_tags` (e.g. the output of `git tag`).

    An empty `existing_tags` — the mirror's very first run, before any release
    has ever been made — is ordinary "not found", not a special case.
    """
    return tag in existing_tags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    current_tag = subcommands.add_parser(
        "current-tag", help="print vX.Y.Z for the version in plugin.json"
    )
    current_tag.add_argument(
        "plugin_json", nargs="?", type=Path, default=DEFAULT_PLUGIN_JSON
    )

    exists = subcommands.add_parser(
        "tag-exists",
        help="exit 0 if TAG is among the given tags, exit 1 otherwise",
    )
    exists.add_argument("tag")
    exists.add_argument("existing_tags", nargs="*", help="e.g. the output of `git tag`")

    args = parser.parse_args(argv)
    if args.command == "current-tag":
        print(tag_for_version(read_version(args.plugin_json)))
        return 0
    if args.command == "tag-exists":
        return 0 if tag_exists(args.tag, args.existing_tags) else 1
    raise AssertionError(f"unhandled command {args.command!r}")  # argparse prevents this


if __name__ == "__main__":
    sys.exit(main())
