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
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from check_version_bump import (
    SKIP_LABEL,
    NotBumped,
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
        with self.assertRaisesRegex(NotBumped, "not been bumped"):
            check_bump((3, 1, 0), (3, 1, 0))

    def test_lower_version_fails(self):
        with self.assertRaises(NotBumped):
            check_bump((3, 1, 0), (3, 0, 9))

    def test_compares_numerically_not_as_strings(self):
        check_bump(parse_version(manifest("3.9.0")), parse_version(manifest("3.10.0")))
        with self.assertRaises(NotBumped):
            check_bump(parse_version(manifest("3.10.0")), parse_version(manifest("3.9.0")))

    def test_message_says_to_run_a_new_pipeline(self):
        with self.assertRaisesRegex(NotBumped, "new pipeline"):
            check_bump((3, 1, 0), (3, 1, 0))


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
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            parse_version("{not json")

    def test_json_non_object_fails(self):
        with self.assertRaisesRegex(ValueError, "not a JSON object"):
            parse_version("[1, 2]")

    def test_error_names_the_source(self):
        with self.assertRaisesRegex(ValueError, "the-target"):
            parse_version("{}", "the-target")


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

    def empty_commit(self):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "work without a bump")

    def run_main(self, labels="", target_ref="main"):
        argv = ["--target-ref", target_ref, "--manifest", "plugin.json", "--labels", labels]
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = main(argv, repo=self.repo)
        return code, out.getvalue(), err.getvalue()

    def test_bumped_branch_passes(self):
        self.commit("3.1.1", "bump")
        self.assertEqual(self.run_main()[0], 0)

    def test_unbumped_branch_fails_with_message(self):
        self.empty_commit()
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("3.1.0", err)

    def test_lower_version_branch_fails(self):
        self.commit("3.0.9", "downgrade")
        self.assertEqual(self.run_main()[0], 1)

    def test_label_skips_unbumped_branch(self):
        self.empty_commit()
        code, out, _ = self.run_main(labels=SKIP_LABEL)
        self.assertEqual(code, 0)
        self.assertIn(SKIP_LABEL, out)

    def test_bad_target_ref_fails_loudly(self):
        code, _, err = self.run_main(target_ref="nope")
        self.assertEqual(code, 3)
        self.assertIn("cannot read versions", err)

    def test_manifest_missing_from_target_ref_fails_loudly(self):
        git(self.repo, "checkout", "-q", "--orphan", "empty-base")
        git(self.repo, "rm", "-q", "-rf", ".")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "no manifest")
        git(self.repo, "checkout", "-q", "feature")
        self.assertEqual(self.run_main(target_ref="empty-base")[0], 3)

    def test_invalid_json_on_branch_fails_loudly(self):
        self.manifest.write_text("{not json", encoding="utf-8")
        code, _, err = self.run_main()
        self.assertEqual(code, 3)
        self.assertIn("on this branch", err)


if __name__ == "__main__":
    unittest.main()
