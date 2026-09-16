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
from contextlib import redirect_stdout
from pathlib import Path

from release_version import main, read_version, tag_exists, tag_for_version


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
    def run_main(self, argv: list[str]) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(argv)
        return exit_code, out.getvalue().strip()

    def test_current_tag_prints_v_prefixed_version(self):
        plugin_json = write_plugin_json("3.1.4")
        code, output = self.run_main(["current-tag", str(plugin_json)])
        self.assertEqual(code, 0)
        self.assertEqual(output, "v3.1.4")

    def test_tag_exists_exit_code_reflects_presence(self):
        code, _ = self.run_main(["tag-exists", "v2.0.0", "v1.0.0", "v2.0.0"])
        self.assertEqual(code, 0)

    def test_tag_exists_exit_code_reflects_absence(self):
        code, _ = self.run_main(["tag-exists", "v2.0.0", "v1.0.0"])
        self.assertEqual(code, 1)

    def test_tag_exists_with_no_tags_is_absence_not_an_error(self):
        code, _ = self.run_main(["tag-exists", "v2.0.0"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
