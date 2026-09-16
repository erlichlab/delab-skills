#!/usr/bin/env python3
"""Version/tag logic for .github/workflows/release.yml.

The workflow needs two decisions on every push to `main` (including the ones
the GitLab -> GitHub mirror cron job makes): what tag this version of the
plugin should have, and whether that tag already exists — the second is what
makes an unbumped push a silent no-op instead of a duplicate-tag failure.
Both are plain string/JSON logic with no GitHub API involved, so they live
here as pure, tested functions rather than inline shell in the YAML.

Exit codes for the CLI matter to the workflow, which branches on them rather
than just testing zero-vs-nonzero: 0 is success (a tag was printed, or the
tag was confirmed to already exist); 1 is `tag-exists` confirming the tag is
genuinely absent, which is the "go ahead and release" case; 2 is argparse's
own usage-error code; anything else (currently 3) is an unexpected failure —
a malformed plugin.json, for instance — which must fail the workflow step
loudly rather than being mistaken for "tag not found" and triggering a
release anyway.

What this script cannot cover, and why: the actual `gh release create` call,
GITHUB_TOKEN permissions, and the mirror push that triggers the workflow all
require a real GitHub repo and Actions run — there is no local stand-in for
them, and as of this writing the workflow has not yet run there for real.
Those parts were checked by manual review of the YAML and the Python unit
tests in scripts/test_release_version.py only — not by an actual triggered
run.

Run the tests with:  python3 -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_PLUGIN_JSON = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "delab-coding-practices"
    / ".claude-plugin"
    / "plugin.json"
)

# Exit codes the workflow branches on (see module docstring).
EXIT_OK = 0
EXIT_NOT_FOUND = 1
# 2 is reserved for argparse's own usage-error exit; do not reuse it here.
EXIT_UNEXPECTED_ERROR = 3

# Digits only, dot-separated, no surrounding whitespace: a git tag is built
# from this by prefixing `v`, and git ref names forbid whitespace and most
# punctuation, so anything looser risks a tag that's malformed or just wrong.
VERSION_RE = re.compile(r"\A\d+\.\d+\.\d+\Z")


def read_version(plugin_json: Path) -> str:
    """The `version` field plugin.json declares.

    Raises if it's missing, empty, or not a plain `X.Y.Z` string — a silent
    default, or a version like `" 2.0.0 "` passed through untouched, would
    tag and release under the wrong (or an invalid) name instead of failing
    where the actual problem is (principle 9).
    """
    manifest = json.loads(plugin_json.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not version:
        raise ValueError(f"{plugin_json}: no `version` field")
    if not VERSION_RE.match(version):
        raise ValueError(
            f"{plugin_json}: version {version!r} is not of the form X.Y.Z"
        )
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
    """Run the CLI, returning an exit code rather than raising.

    Errors are caught here, not left to propagate, so that calling `main()`
    directly (as the tests do) sees the same exit-code contract the workflow
    relies on to tell "tag genuinely not found" (1) apart from "something
    went wrong" (3) — see EXIT_UNEXPECTED_ERROR above. A malformed CLI
    invocation is the one exception: argparse raises `SystemExit(2)` itself,
    which is left to propagate unchanged.
    """
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
        help=(
            f"exit {EXIT_OK} if TAG is among the given tags, "
            f"exit {EXIT_NOT_FOUND} if it is confirmed absent"
        ),
    )
    exists.add_argument("tag")
    exists.add_argument("existing_tags", nargs="*", help="e.g. the output of `git tag`")

    args = parser.parse_args(argv)  # SystemExit(2) on bad usage, left to propagate
    try:
        if args.command == "current-tag":
            print(tag_for_version(read_version(args.plugin_json)))
            return EXIT_OK
        if args.command == "tag-exists":
            found = tag_exists(args.tag, args.existing_tags)
            return EXIT_OK if found else EXIT_NOT_FOUND
        raise AssertionError(f"unhandled command {args.command!r}")  # argparse prevents this
    except Exception as exc:
        print(f"release_version.py {args.command}: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED_ERROR


if __name__ == "__main__":
    sys.exit(main())
