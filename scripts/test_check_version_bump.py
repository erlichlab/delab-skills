#!/usr/bin/env python3
"""Tests for the merge-request version-bump check.

Run with:  python3 -m unittest discover -s scripts -p 'test_*.py'

The GitLab job wiring (rules, fetching the target branch) cannot run here;
the git-backed tests below exercise the same `git show <ref>:<path>` call
against a throwaway repository instead.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from check_version_bump import (
    SKIP_LABEL,
    check_bump,
    main,
    parse_version,
    skip_requested,
)


def manifest(version) -> str:
    return json.dumps({"name": "x", "version": version})


class CheckBumpTests(unittest.TestCase):
    def test_bumped_passes(self):
        check_bump((3, 1, 0), (3, 1, 1))
        check_bump((3, 1, 9), (3, 2, 0))
        check_bump((3, 9, 9), (4, 0, 0))

    def test_same_version_fails(self):
        with self.assertRaisesRegex(ValueError, "not been bumped"):
            check_bump((3, 1, 0), (3, 1, 0))

    def test_lower_version_fails(self):
        with self.assertRaises(ValueError):
            check_bump((3, 1, 0), (3, 0, 9))

    def test_compares_numerically_not_as_strings(self):
        check_bump(parse_version(manifest("3.9.0")), parse_version(manifest("3.10.0")))
        with self.assertRaises(ValueError):
            check_bump(parse_version(manifest("3.10.0")), parse_version(manifest("3.9.0")))


class ParseVersionTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_version(manifest("3.10.2")), (3, 10, 2))

    def test_missing_version_fails(self):
        with self.assertRaisesRegex(ValueError, "version"):
            parse_version(json.dumps({"name": "x"}))

    def test_invalid_version_fails(self):
        for bad in ("3.1", "v3.1.0", "3.1.0-rc1", "", 3, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_version(manifest(bad))

    def test_invalid_json_fails(self):
        with self.assertRaises(ValueError):
            parse_version("{not json")


class SkipLabelTests(unittest.TestCase):
    def test_label_present(self):
        self.assertTrue(skip_requested(f"bug,{SKIP_LABEL}"))
        self.assertTrue(skip_requested(f"bug, {SKIP_LABEL}"))

    def test_label_absent(self):
        self.assertFalse(skip_requested(""))
        self.assertFalse(skip_requested("bug,no-release-notes"))


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo, check=True, capture_output=True,
    )


class MainTests(unittest.TestCase):
    """End to end against a real repo: `main` is the target, HEAD the MR branch."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.manifest = self.repo / "plugin.json"
        git(self.repo, "init", "-q", "-b", "main")
        self.commit("3.1.0", "base")
        git(self.repo, "checkout", "-q", "-b", "feature")

    def commit(self, version, msg):
        self.manifest.write_text(manifest(version), encoding="utf-8")
        git(self.repo, "add", "plugin.json")
        git(self.repo, "commit", "-q", "-m", msg)

    def run_main(self, labels=""):
        argv = ["--target-ref", "main", "--manifest", "plugin.json", "--labels", labels]
        with redirect_stderr(io.StringIO()) as err:
            code = main(argv, repo=self.repo)
        return code, err.getvalue()

    def test_bumped_branch_passes(self):
        self.commit("3.1.1", "bump")
        self.assertEqual(self.run_main()[0], 0)

    def test_unbumped_branch_fails_with_message(self):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "work without a bump")
        code, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("3.1.0", err)

    def test_label_skips_unbumped_branch(self):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "work without a bump")
        self.assertEqual(self.run_main(labels=SKIP_LABEL)[0], 0)

    def test_bad_target_ref_fails_loudly(self):
        argv = ["--target-ref", "nope", "--manifest", "plugin.json"]
        with redirect_stderr(io.StringIO()):
            self.assertNotEqual(main(argv, repo=self.repo), 0)


if __name__ == "__main__":
    unittest.main()
