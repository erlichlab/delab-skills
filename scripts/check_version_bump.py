#!/usr/bin/env python3
"""Fail a merge request whose plugin version is not above the target branch's.

Principle 13 says every merge request bumps `version` in plugin.json; a
forgotten bump silently makes no GitHub release. The GitLab `version-bump`
job runs this on merge request pipelines.

Versions are compared as (MAJOR, MINOR, PATCH) integer tuples, so 3.10.0 is
above 3.9.0. An MR labelled `no-release` is exempt (docs-only changes and
the like); GitLab exposes the labels as CI_MERGE_REQUEST_LABELS.

Exit codes: 0 pass or skipped; 1 version not bumped; 3 anything else wrong
(unreadable target ref, malformed plugin.json) -- never mistaken for a pass.

Run the tests with:  python3 -m unittest discover -s scripts -p 'test_*.py'
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from release_version import VERSION_RE

SKIP_LABEL = "no-release"
DEFAULT_MANIFEST = "plugins/delab-coding-practices/.claude-plugin/plugin.json"

EXIT_OK = 0
EXIT_NOT_BUMPED = 1
EXIT_ERROR = 3


class NotBumped(ValueError):
    """The version is valid but not above the target branch's."""


def parse_version(manifest_text: str) -> tuple[int, int, int]:
    """The (MAJOR, MINOR, PATCH) a plugin.json text declares; raises if absent or not X.Y.Z."""
    try:
        version = json.loads(manifest_text).get("version")
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"plugin.json is not a JSON object: {exc}") from exc
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise ValueError(f"`version` is missing or not of the form X.Y.Z: {version!r}")
    major, minor, patch = map(int, version.split("."))
    return major, minor, patch


def check_bump(target: tuple[int, int, int], new: tuple[int, int, int]) -> None:
    """Raise unless `new` is strictly greater than `target`."""
    if new <= target:
        fmt = lambda v: ".".join(map(str, v))
        raise NotBumped(
            f"version {fmt(new)} has not been bumped above the target branch's "
            f"{fmt(target)}; bump `version` in plugin.json (principle 13), or "
            f"add the `{SKIP_LABEL}` label to this merge request."
        )


def skip_requested(labels: str) -> bool:
    """Whether a comma-separated label list (CI_MERGE_REQUEST_LABELS) has the skip label."""
    return SKIP_LABEL in (label.strip() for label in labels.split(","))


def read_at_ref(repo: Path, ref: str, path: str) -> str:
    """File contents at a git ref; raises CalledProcessError if ref or path is missing."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    return result.stdout


def main(argv: list[str] | None = None, repo: Path = Path(".")) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target-ref", required=True, help="git ref of the target branch")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="plugin.json path in the repo")
    parser.add_argument("--labels", default="", help="comma-separated MR labels")
    args = parser.parse_args(argv)

    if skip_requested(args.labels):
        print(f"`{SKIP_LABEL}` label present: skipping the version-bump check.")
        return EXIT_OK
    try:
        target = parse_version(read_at_ref(repo, args.target_ref, args.manifest))
        new = parse_version((repo / args.manifest).read_text(encoding="utf-8"))
        check_bump(target, new)
    except NotBumped as exc:
        print(f"check_version_bump.py: {exc}", file=sys.stderr)
        return EXIT_NOT_BUMPED
    except ValueError as exc:
        print(f"check_version_bump.py: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = getattr(exc, "stderr", "") or exc
        print(f"check_version_bump.py: cannot read versions: {detail}", file=sys.stderr)
        return EXIT_ERROR
    print("Version bumped.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
