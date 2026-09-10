#!/usr/bin/env python3
"""Tests for the plugin layout checker.

Run with:  python3 -m unittest discover -s scripts -p 'test_*.py'

The checker's job is to reject a plugin that agents would reject, so a bug that
wrongly *accepts* input is invisible to CI: running the checker against this
repo's own valid tree passes either way. These tests supply the invalid inputs
the repo does not contain.

Uses `unittest` rather than pytest for the same reason the checker uses only the
standard library — no environment to create on a bare clone.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_plugin import (
    SKILL_DESCRIPTION_MAX,
    check_frontmatter_yaml,
    check_skill_description,
    check_skill_frontmatter,
    check_skill_name,
    parse_frontmatter,
)


def frontmatter(body: str) -> str:
    return f"---\n{body}\n---\n\nBody text.\n"


class ParseFrontmatter(unittest.TestCase):
    def test_plain_scalars(self):
        fields = parse_frontmatter(frontmatter("name: demo\ndescription: A demo."))
        self.assertEqual(fields, {"name": "demo", "description": "A demo."})

    def test_stops_at_the_next_field(self):
        """A field must not absorb the block scalar of the field below it."""
        fields = parse_frontmatter(
            frontmatter("name: demo\ndescription: >-\n  first\n  second")
        )
        self.assertEqual(fields["name"], "demo")
        self.assertEqual(fields["description"], "first second")

    def test_blank_line_does_not_truncate_a_folded_scalar(self):
        """A blank line is the paragraph break inside `>-`, not the end of it."""
        fields = parse_frontmatter(
            frontmatter("description: >-\n  first para\n\n  second para\nname: demo")
        )
        self.assertEqual(fields["description"], "first para second para")
        self.assertEqual(fields["name"], "demo")

    def test_leading_hyphen_survives_parsing(self):
        """`-demo` must reach the name check as `-demo`, not be normalised away."""
        self.assertEqual(parse_frontmatter(frontmatter("name: -demo"))["name"], "-demo")

    def test_quoted_scalar(self):
        self.assertEqual(parse_frontmatter(frontmatter('name: "demo"'))["name"], "demo")
        self.assertEqual(parse_frontmatter(frontmatter("name: 'demo'"))["name"], "demo")

    def test_list_value_does_not_leak_into_the_field_above(self):
        fields = parse_frontmatter(
            frontmatter("description: A demo.\ntools:\n  - Read\n  - Write")
        )
        self.assertEqual(fields["description"], "A demo.")

    def test_present_but_empty_is_not_absent(self):
        self.assertEqual(parse_frontmatter(frontmatter("name:"))["name"], "")

    def test_no_frontmatter_block(self):
        self.assertEqual(parse_frontmatter("# Just a heading\n"), {})

    def test_quotes_inside_a_block_scalar_are_literal_text(self):
        fields = parse_frontmatter(
            frontmatter('description: >-\n  "Load this" when you see "foo"')
        )
        self.assertEqual(fields["description"], '"Load this" when you see "foo"')


class CheckSkillName(unittest.TestCase):
    def test_valid(self):
        name = "delab-coding-practices"
        self.assertEqual(check_skill_name(name, name), [])

    def test_absent_and_empty_are_distinguished(self):
        self.assertIn("has no `name`", check_skill_name(None, "demo")[0])
        self.assertIn("is empty", check_skill_name("", "demo")[0])

    def test_spec_invalid_examples(self):
        """The three names the spec itself lists as invalid, plus a trailing hyphen."""
        for name in ("PDF-Processing", "-pdf", "pdf--processing", "demo-"):
            with self.subTest(name=name):
                problems = check_skill_name(name, name)
                self.assertTrue(
                    any("the spec allows only lowercase" in p for p in problems),
                    f"{name} should be rejected for its format, got {problems}",
                )

    def test_too_long(self):
        name = "a" * 65
        self.assertTrue(any("caps it at 64" in p for p in check_skill_name(name, name)))
        self.assertEqual(check_skill_name("a" * 64, "a" * 64), [])

    def test_must_match_directory(self):
        problems = check_skill_name("demo", "other-dir")
        self.assertEqual(len(problems), 1)
        self.assertIn("requires them to match", problems[0])


class CheckFrontmatterYaml(unittest.TestCase):
    def test_unquoted_colon(self):
        problems = check_frontmatter_yaml(
            frontmatter("description: Use this when: the user asks")
        )
        self.assertTrue(any("unquoted colon" in p for p in problems))

    def test_colon_is_legal_when_quoted_or_folded(self):
        for body in ('description: "when: x"', "description: >-\n  when: x"):
            with self.subTest(body=body):
                self.assertEqual(check_frontmatter_yaml(frontmatter(body)), [])

    def test_url_is_not_a_nested_key(self):
        """A colon not followed by a space is legal in a plain scalar."""
        self.assertEqual(
            check_frontmatter_yaml(frontmatter("description: see https://x.com")), []
        )

    def test_tab_indentation(self):
        problems = check_frontmatter_yaml(frontmatter("description: >-\n\tone"))
        self.assertEqual(len(problems), 1)
        self.assertIn("tab", problems[0])


class CheckSkillFrontmatter(unittest.TestCase):
    """The file-reading wrapper: covers what the pure checks cannot."""

    def write_skill(self, body: str, dirname: str = "demo") -> Path:
        skill_dir = Path(tempfile.mkdtemp()) / dirname
        skill_dir.mkdir(parents=True)
        path = skill_dir / "SKILL.md"
        path.write_text(frontmatter(body), encoding="utf-8")
        return path

    def test_valid_skill(self):
        self.assertEqual(
            check_skill_frontmatter(
                self.write_skill("name: demo\ndescription: A demo.")
            ),
            [],
        )

    def test_no_frontmatter_reports_once(self):
        path = self.write_skill("name: demo\ndescription: A demo.")
        path.write_text("# Just a heading\n", encoding="utf-8")
        problems = check_skill_frontmatter(path)
        self.assertEqual(len(problems), 1)
        self.assertIn("no parseable YAML frontmatter", problems[0])

    def test_name_is_compared_against_the_containing_directory(self):
        """The directory comes from the filesystem, not from the frontmatter."""
        path = self.write_skill("name: demo\ndescription: A demo.", dirname="other")
        problems = check_skill_frontmatter(path)
        self.assertTrue(any("the directory is 'other'" in p for p in problems))

    def test_problems_are_prefixed_with_the_path(self):
        path = self.write_skill("description: A demo.")
        problems = check_skill_frontmatter(path)
        self.assertTrue(all(p.startswith(f"{path}: ") for p in problems))


class CheckSkillDescription(unittest.TestCase):
    def test_missing(self):
        self.assertTrue(check_skill_description(None))
        self.assertTrue(check_skill_description(""))

    def test_length_boundary(self):
        self.assertEqual(check_skill_description("x" * SKILL_DESCRIPTION_MAX), [])
        over = check_skill_description("x" * (SKILL_DESCRIPTION_MAX + 1))
        self.assertTrue(any("caps it at 1024" in p for p in over))


if __name__ == "__main__":
    unittest.main()
