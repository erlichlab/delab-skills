#!/usr/bin/env python3
"""Tests for the release-tagging helper used by .github/workflows/release.yml.

Run with:  python3 -m unittest discover -s scripts -p 'test_*.py'

The GitHub Actions run itself (the actual `gh release create` call, the
mirror push that triggers it) cannot run inside this repo's test suite — see
the module docstring in release_version.py. These tests cover everything the
workflow delegates to Python: reading the version and deciding whether a tag
already exists. That split is the point of pulling this out of YAML at all.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from release_version import (
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_UNEXPECTED_ERROR,
    main,
    read_version,
    tag_exists,
    tag_for_version,
)


def write_plugin_json(version: str | None) -> Path:
    manifest = {"name": "demo"} if version is None else {"name": "demo", "version": version}
    path = Path(tempfile.mkdtemp()) / "plugin.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class ReadVersion(unittest.TestCase):
    def test_reads_the_version_field(self):
        self.assertEqual(read_version(write_plugin_json("2.0.0")), "2.0.0")

    def test_missing_field_fails_loudly(self):
        """No silent default — a plugin.json with no version is a bug to surface."""
        with self.assertRaises(ValueError):
            read_version(write_plugin_json(None))

    def test_empty_value_fails_loudly(self):
        with self.assertRaises(ValueError):
            read_version(write_plugin_json(""))

    def test_malformed_version_fails_loudly(self):
        """`" 2.0.0 "` must not silently become tag `" v 2.0.0 "` downstream."""
        for bad in (" 2.0.0 ", "2.0", "v2.0.0", "2.0.0-beta", "2.0.0\n", "latest"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    read_version(write_plugin_json(bad))


class TagForVersion(unittest.TestCase):
    def test_prefixes_with_v(self):
        self.assertEqual(tag_for_version("2.0.0"), "v2.0.0")


class TagExists(unittest.TestCase):
    def test_present_among_other_tags(self):
        self.assertTrue(tag_exists("v2.0.0", ["v1.0.0", "v2.0.0", "v1.9.0"]))

    def test_absent(self):
        self.assertFalse(tag_exists("v2.0.0", ["v1.0.0", "v1.9.0"]))

    def test_no_tags_at_all(self):
        """The mirror's first-ever run: `git tag` lists nothing, not a crash."""
        self.assertFalse(tag_exists("v2.0.0", []))


class Cli(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(argv)
        return exit_code, out.getvalue().strip()

    def run_main_capturing_stderr(self, argv: list[str]) -> tuple[int, str]:
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            exit_code = main(argv)
        return exit_code, err.getvalue().strip()

    def test_current_tag_prints_v_prefixed_version(self):
        plugin_json = write_plugin_json("3.1.4")
        code, output = self.run_main(["current-tag", str(plugin_json)])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(output, "v3.1.4")

    def test_tag_exists_exit_code_reflects_presence(self):
        code, _ = self.run_main(["tag-exists", "v2.0.0", "v1.0.0", "v2.0.0"])
        self.assertEqual(code, EXIT_OK)

    def test_tag_exists_exit_code_reflects_absence(self):
        code, _ = self.run_main(["tag-exists", "v2.0.0", "v1.0.0"])
        self.assertEqual(code, EXIT_NOT_FOUND)

    def test_tag_exists_with_no_tags_is_absence_not_an_error(self):
        code, _ = self.run_main(["tag-exists", "v2.0.0"])
        self.assertEqual(code, EXIT_NOT_FOUND)

    def test_current_tag_crash_is_distinguishable_from_not_found(self):
        """A malformed plugin.json must not exit 1 — that means "tag not found"
        to the workflow's `if`, which would make it attempt a release with an
        empty/garbage tag instead of failing the step (reviewer finding 1/2)."""
        plugin_json = write_plugin_json(None)  # no `version` field: read_version raises
        code, stderr = self.run_main_capturing_stderr(["current-tag", str(plugin_json)])
        self.assertEqual(code, EXIT_UNEXPECTED_ERROR)
        self.assertNotEqual(code, EXIT_NOT_FOUND)
        self.assertIn("version", stderr)

    def test_exit_codes_are_pairwise_distinct(self):
        self.assertEqual(len({EXIT_OK, EXIT_NOT_FOUND, EXIT_UNEXPECTED_ERROR, 2}), 4)

    def test_bad_subcommand_is_argparse_usage_error(self):
        """Usage errors (exit 2) are argparse's own and must stay distinct too."""
        with self.assertRaises(SystemExit) as cm:
            main(["not-a-real-command"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
