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

import json
import tempfile
import unittest
from pathlib import Path

from check_plugin import (
    SKILL_DESCRIPTION_MAX,
    check_agent_frontmatter,
    check_agent_isolation,
    check_all_mentions,
    check_command_mentions,
    check_frontmatter_yaml,
    check_links,
    check_manifest_paths,
    check_marketplace,
    check_plugin_root_refs,
    check_skill_description,
    check_skill_frontmatter,
    check_skill_name,
    find_unclosed_fence,
    heading_anchors,
    load_json,
    parse_frontmatter,
    plugin_component_names,
    slugify,
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


class CheckAgentFrontmatter(unittest.TestCase):
    def write_agent(self, body: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "agent.md"
        path.write_text(frontmatter(body), encoding="utf-8")
        return path

    def check(self, body: str) -> list[str]:
        return check_agent_frontmatter(self.write_agent(body))

    def test_valid_values(self):
        writer = "tools:\n  - Write\nisolation: worktree\n"
        for body in (
            f"name: a\nmodel: sonnet\n{writer}",
            f"name: a\nmodel: claude-opus-5\n{writer}",
            f"name: a\nmodel: opus[1m]\n{writer}",
            "name: a\nmodel: inherit",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.check(body), [])

    def test_remote_isolation_is_valid(self):
        """`remote` is the other isolation mode the loader accepts."""
        body = "name: a\ntools:\n  - Write\nisolation: remote"
        self.assertEqual(self.check(body), [])

    def test_isolation_typo_is_caught(self):
        """`worktrees` is ignored by the loader, silently un-isolating the agent."""
        problems = self.check("name: a\ntools:\n  - Write\nisolation: worktrees")
        self.assertTrue(any("shared working tree" in p for p in problems))

    def test_unknown_model_alias(self):
        self.assertTrue(any("expected one of" in p for p in self.check("name: a\nmodel: sonet")))

    def test_wrong_case_is_rejected(self):
        """YAML is case-sensitive; a mis-cased value risks being dropped."""
        for body in ("name: a\nmodel: Sonnet", "name: a\ntools:\n  - Write\nisolation: Worktree"):
            with self.subTest(body=body):
                self.assertTrue(self.check(body))

    def test_empty_value_is_not_silently_accepted(self):
        self.assertTrue(any("empty" in p for p in self.check("name: a\nmodel:")))

    def test_inline_comment_does_not_trip_the_check(self):
        body = "name: a\nmodel: sonnet # cheap\ntools:\n  - Write\nisolation: worktree # own tree"
        self.assertEqual(self.check(body), [])

    def test_problems_are_prefixed_with_the_path(self):
        path = self.write_agent("name: a\nmodel: sonet")
        self.assertTrue(all(p.startswith(f"{path}: ") for p in check_agent_frontmatter(path)))


class CheckAgentIsolation(unittest.TestCase):
    """The invariant the design rests on, which a spelling check cannot see."""

    def test_writer_without_isolation(self):
        problems = check_agent_isolation({"tools": "- Read - Write - Edit"})
        self.assertTrue(any("shared working tree" in p for p in problems))

    def test_reader_with_isolation(self):
        problems = check_agent_isolation(
            {"tools": "- Read - Grep", "isolation": "worktree"}
        )
        self.assertTrue(any("cannot see the work" in p for p in problems))

    def test_remote_counts_as_isolated(self):
        """Neither mode leaves the agent in the shared checkout."""
        self.assertEqual(
            check_agent_isolation({"tools": "- Write", "isolation": "remote"}), []
        )
        self.assertTrue(check_agent_isolation({"tools": "- Read", "isolation": "remote"}))

    def test_correct_pairings(self):
        self.assertEqual(
            check_agent_isolation({"tools": "- Read - Write", "isolation": "worktree"}), []
        )
        self.assertEqual(check_agent_isolation({"tools": "- Read - Grep"}), [])


class CheckCommandMentions(unittest.TestCase):
    """A `/delab-…` in prose is invisible to the link checker, so check it here."""

    def build(self, doc: str, commands=(), skills=()) -> tuple[Path, set[str]]:
        root = Path(tempfile.mkdtemp())
        (root / "doc.md").write_text(doc, encoding="utf-8")
        return root, set(commands) | set(skills)

    def test_existing_command_and_skill_pass(self):
        root, names = self.build(
            "Run `/delab-review` or `/delab-coding-practices:delab-agentic-workflow`.",
            commands=["delab-review"],
            skills=["delab-agentic-workflow"],
        )
        self.assertEqual(check_command_mentions(root, names), [])

    def test_deleted_command_is_caught(self):
        root, names = self.build("Run `/delab-enforce-style`.", commands=["delab-review"])
        self.assertTrue(any("delab-enforce-style" in p for p in check_command_mentions(root, names)))

    def test_bare_slash_mention_without_backticks(self):
        root, names = self.build("Just run /delab-gone to start.", commands=["delab-review"])
        self.assertTrue(any("delab-gone" in p for p in check_command_mentions(root, names)))

    def test_renamed_skill_referred_to_by_bare_name(self):
        """The form skills use for each other — the reason this check exists."""
        root, names = self.build("See the `delab-practises` skill.", skills=["delab-practices"])
        self.assertTrue(any("delab-practises" in p for p in check_command_mentions(root, names)))

    def test_names_are_pooled_not_checked_per_plugin(self):
        """A second plugin's commands must not make the first plugin's look missing."""
        root, _ = self.build("`/delab-a` and `/delab-b`.")
        self.assertEqual(check_command_mentions(root, {"delab-a", "delab-b"}), [])

    def test_claude_directory_is_skipped(self):
        """Subagent worktrees live there; they are not repo content."""
        root, names = self.build("fine", commands=["delab-review"])
        worktree = root / ".claude" / "worktrees" / "w"
        worktree.mkdir(parents=True)
        (worktree / "stale.md").write_text("`/delab-gone`", encoding="utf-8")
        self.assertEqual(check_command_mentions(root, names), [])


class PluginComponentNames(unittest.TestCase):
    """The repo's own name must come from `repository` in plugin.json, not the
    checkout directory's name — that is the repo's name only by coincidence,
    and a subagent's worktree or any differently named clone breaks it."""

    def build_repo(self, repository: str) -> Path:
        root = Path(tempfile.mkdtemp())
        plugin_dir = root / "plugins" / "demo"
        (plugin_dir / ".claude-plugin").mkdir(parents=True)
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "demo", "repository": repository}), encoding="utf-8"
        )
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps(
                {"name": "mkt", "plugins": [{"name": "demo", "source": "./plugins/demo"}]}
            ),
            encoding="utf-8",
        )
        return root

    def test_repo_name_comes_from_manifest_not_checkout_dirname(self):
        root = self.build_repo("https://github.com/erlichlab/delab-skills")
        names, problems = plugin_component_names(root)
        self.assertIn("delab-skills", names)
        self.assertNotIn(root.name, names)
        self.assertEqual(problems, [])

    def test_mention_of_repo_name_accepted_regardless_of_checkout_dirname(self):
        """The fixture's temp dir is never named `delab-skills`; the mention
        must still resolve via the manifest's `repository` field."""
        root = self.build_repo("https://github.com/erlichlab/delab-skills")
        (root / "doc.md").write_text("See `delab-skills` for details.", encoding="utf-8")
        self.assertEqual(check_all_mentions(root), [])

    def test_misspelt_repo_name_is_still_reported(self):
        root = self.build_repo("https://github.com/erlichlab/delab-skills")
        (root / "doc.md").write_text("See `delab-skils` for details.", encoding="utf-8")
        problems = check_all_mentions(root)
        self.assertTrue(any("delab-skils" in p for p in problems))

    def test_non_string_repository_is_reported_not_raised(self):
        """A plausible typo — `repository` nested under a stray `url` key, or
        any non-string JSON value — must surface as a normal FAIL, not an
        AttributeError that aborts the whole checker run before it can report
        anything else."""
        root = self.build_repo({"url": "https://github.com/erlichlab/delab-skills"})
        names, problems = plugin_component_names(root)
        self.assertEqual(names, set())
        self.assertTrue(any("repository" in p and "string" in p for p in problems))

    def test_non_string_repository_does_not_crash_check_all_mentions(self):
        root = self.build_repo(["https://github.com/erlichlab/delab-skills"])
        problems = check_all_mentions(root)
        self.assertTrue(any("repository" in p and "string" in p for p in problems))


class HeadingAnchors(unittest.TestCase):
    """A `#` line inside a fenced code block is a comment, not a heading."""

    def test_fenced_comment_is_not_an_anchor(self):
        text = "# Real Heading\n\n```python\n# load data\n```\n"
        self.assertEqual(heading_anchors(text), {"real-heading"})

    def test_heading_after_a_closed_fence_still_counts(self):
        text = "```python\n# not a heading\n```\n\n# Load Data\n"
        self.assertEqual(heading_anchors(text), {"load-data"})

    def test_mismatched_fence_type_inside_does_not_close_the_outer_fence(self):
        """A ``` example nested in a ~~~ fence must not toggle the state off."""
        text = (
            "# Real Heading\n\n"
            "~~~text\n"
            "example:\n"
            "```python\n"
            "# load data\n"
            "```\n"
            "~~~\n"
        )
        self.assertEqual(heading_anchors(text), {"real-heading"})

    def test_shorter_fence_of_the_same_type_inside_does_not_close_the_outer_fence(self):
        """CommonMark requires a closer at least as long as its opener."""
        text = (
            "# Real Heading\n\n"
            "````text\n"
            "example:\n"
            "```python\n"
            "# load data\n"
            "```\n"
            "````\n"
        )
        self.assertEqual(heading_anchors(text), {"real-heading"})

    def test_unclosed_fence_swallows_headings_after_it(self):
        """CommonMark: an unterminated fence runs to end of file."""
        text = "```python\n# load data\n\n# Load Data\n"
        self.assertEqual(heading_anchors(text), set())


class FindUnclosedFence(unittest.TestCase):
    def test_closed_fence_reports_none(self):
        self.assertIsNone(find_unclosed_fence("```python\n# x\n```\n"))

    def test_unclosed_fence_reports_its_opening_line(self):
        text = "intro\n\n```python\n# x\n"
        self.assertEqual(find_unclosed_fence(text), 3)

    def test_no_fence_reports_none(self):
        self.assertIsNone(find_unclosed_fence("# Heading\n\nbody\n"))


class CheckLinksFencedAnchors(unittest.TestCase):
    """Regression for issue #8: a fenced-code comment must not satisfy a link."""

    def build(self, other_body: str, link_target: str) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "other.md").write_text(other_body, encoding="utf-8")
        (root / "doc.md").write_text(f"[see]({link_target})\n", encoding="utf-8")
        return root

    def test_link_to_fenced_comment_only_anchor_is_dead(self):
        root = self.build("```python\n# load data\n```\n", "other.md#load-data")
        problems = check_links(root)
        self.assertTrue(any("dead anchor" in p for p in problems))

    def test_link_to_real_heading_passes(self):
        root = self.build("# Load Data\n", "other.md#load-data")
        self.assertEqual(check_links(root), [])

    def test_link_into_an_unclosed_fence_names_the_real_cause(self):
        """The generic 'dead anchor' message would hide an unclosed fence as
        the actual cause; the checker must call it out instead of leaving the
        reader to assume the heading is simply missing (principle 9)."""
        root = self.build("```python\n# load data\n\n# Load Data\n", "other.md#load-data")
        problems = check_links(root)
        self.assertTrue(any("unclosed fenced code block" in p for p in problems))


class CheckSkillDescription(unittest.TestCase):
    def test_missing(self):
        self.assertTrue(check_skill_description(None))
        self.assertTrue(check_skill_description(""))

    def test_length_boundary(self):
        self.assertEqual(check_skill_description("x" * SKILL_DESCRIPTION_MAX), [])
        over = check_skill_description("x" * (SKILL_DESCRIPTION_MAX + 1))
        self.assertTrue(any("caps it at 1024" in p for p in over))


class CheckManifestPaths(unittest.TestCase):
    """The !13 breakage: a directory value in `commands`/`agents` makes
    `/plugin install` fail for every user, with no error anywhere else."""

    def make_plugin_dir(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_directory_value_is_the_13_breakage(self):
        """`"agents": "./agents"` is exactly what broke installs in !13."""
        plugin_dir = self.make_plugin_dir()
        (plugin_dir / "agents").mkdir()
        problems = check_manifest_paths(plugin_dir, {"agents": "./agents"})
        self.assertTrue(any("a directory" in p for p in problems))

    def test_list_of_existing_md_files_passes(self):
        plugin_dir = self.make_plugin_dir()
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "foo.md").write_text("# Foo\n", encoding="utf-8")
        (commands_dir / "bar.md").write_text("# Bar\n", encoding="utf-8")
        manifest = {"commands": ["commands/foo.md", "commands/bar.md"]}
        self.assertEqual(check_manifest_paths(plugin_dir, manifest), [])

    def test_listed_md_file_that_does_not_exist_is_reported(self):
        plugin_dir = self.make_plugin_dir()
        manifest = {"commands": ["commands/missing.md"]}
        problems = check_manifest_paths(plugin_dir, manifest)
        self.assertTrue(any("does not exist" in p for p in problems))

    def test_field_absent_is_not_an_error(self):
        """Dropping the field entirely is the documented fix — it must pass."""
        self.assertEqual(check_manifest_paths(self.make_plugin_dir(), {}), [])


class Slugify(unittest.TestCase):
    def test_lowercases_and_hyphenates_spaces(self):
        self.assertEqual(slugify("## Some Heading"), "some-heading")

    def test_strips_punctuation(self):
        self.assertEqual(slugify("# It's a Test: v2!"), "its-a-test-v2")

    def test_underscores_fold_into_hyphens_like_whitespace(self):
        """`slugify` has no separate underscore case: `[\\s_]+` folds an
        underscore run together with whitespace into one hyphen, same as a
        space would. A literal hyphen in the heading is left alone."""
        self.assertEqual(slugify("# check_manifest_paths"), "check-manifest-paths")
        self.assertEqual(slugify("# already-hyphenated"), "already-hyphenated")


class CheckLinks(unittest.TestCase):
    def make_root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_missing_file_is_reported(self):
        root = self.make_root()
        (root / "doc.md").write_text("See [gone](nonexistent.md).\n", encoding="utf-8")
        problems = check_links(root)
        self.assertTrue(any("dead link" in p for p in problems))

    def test_missing_anchor_is_reported(self):
        root = self.make_root()
        (root / "other.md").write_text("# Real Heading\n", encoding="utf-8")
        (root / "doc.md").write_text(
            "See [it](other.md#not-a-real-heading).\n", encoding="utf-8"
        )
        problems = check_links(root)
        self.assertTrue(any("dead anchor" in p for p in problems))

    def test_valid_link_with_anchor_passes(self):
        root = self.make_root()
        (root / "other.md").write_text("# Real Heading\n", encoding="utf-8")
        (root / "doc.md").write_text(
            "See [it](other.md#real-heading).\n", encoding="utf-8"
        )
        self.assertEqual(check_links(root), [])

    def test_external_and_mailto_links_are_not_checked(self):
        root = self.make_root()
        (root / "doc.md").write_text(
            "See [x](https://example.com/nope) or [y](mailto:a@b.com).\n",
            encoding="utf-8",
        )
        self.assertEqual(check_links(root), [])


class CheckPluginRootRefs(unittest.TestCase):
    """`${CLAUDE_PLUGIN_ROOT}/...` paths a command tells the agent to read."""

    def write_command(self, plugin_dir: Path, text: str) -> None:
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        (commands_dir / "cmd.md").write_text(text, encoding="utf-8")

    def test_missing_target_is_reported(self):
        plugin_dir = Path(tempfile.mkdtemp())
        self.write_command(
            plugin_dir, "Read ${CLAUDE_PLUGIN_ROOT}/skills/demo/SKILL.md now.\n"
        )
        problems = check_plugin_root_refs(plugin_dir)
        self.assertTrue(any("skills/demo/SKILL.md does not exist" in p for p in problems))

    def test_existing_target_passes(self):
        plugin_dir = Path(tempfile.mkdtemp())
        skill_dir = plugin_dir / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
        self.write_command(
            plugin_dir, "Read ${CLAUDE_PLUGIN_ROOT}/skills/demo/SKILL.md now.\n"
        )
        self.assertEqual(check_plugin_root_refs(plugin_dir), [])

    def test_placeholder_ref_checks_only_the_parent_directory(self):
        """`languages/<lang>.md` is filled in by the agent, so only
        `languages/` — not the literal placeholder file — must exist."""
        plugin_dir = Path(tempfile.mkdtemp())
        (plugin_dir / "languages").mkdir(parents=True)
        self.write_command(
            plugin_dir, "Read ${CLAUDE_PLUGIN_ROOT}/languages/<lang>.md now.\n"
        )
        self.assertEqual(check_plugin_root_refs(plugin_dir), [])


class LoadJson(unittest.TestCase):
    def test_missing_file_is_reported(self):
        data, problems = load_json(Path(tempfile.mkdtemp()) / "gone.json")
        self.assertIsNone(data)
        self.assertTrue(any("missing" in p for p in problems))

    def test_invalid_json_is_reported(self):
        path = Path(tempfile.mkdtemp()) / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        data, problems = load_json(path)
        self.assertIsNone(data)
        self.assertTrue(any("invalid JSON" in p for p in problems))

    def test_valid_json_parses_with_no_problems(self):
        path = Path(tempfile.mkdtemp()) / "good.json"
        path.write_text('{"name": "demo"}', encoding="utf-8")
        data, problems = load_json(path)
        self.assertEqual(data, {"name": "demo"})
        self.assertEqual(problems, [])


class CheckMarketplace(unittest.TestCase):
    """The catalog (marketplace.json) and every manifest it points at."""

    def make_root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def write_marketplace(self, root: Path, data: dict) -> None:
        marketplace_dir = root / ".claude-plugin"
        marketplace_dir.mkdir(parents=True, exist_ok=True)
        (marketplace_dir / "marketplace.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def make_valid_plugin(self, root: Path, name: str) -> None:
        """A minimal plugin with no problems of its own to report."""
        plugin_dir = root / name
        (plugin_dir / ".claude-plugin").mkdir(parents=True)
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "description": "A demo plugin."}),
            encoding="utf-8",
        )
        skill_dir = plugin_dir / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo\ndescription: A demo.\n---\n\nBody.\n", encoding="utf-8"
        )

    def test_missing_marketplace_name_is_reported(self):
        root = self.make_root()
        self.write_marketplace(root, {"plugins": []})
        problems = check_marketplace(root)
        self.assertTrue(any("missing `name`" in p for p in problems))

    def test_entry_missing_source_is_reported(self):
        root = self.make_root()
        self.write_marketplace(
            root, {"name": "cat", "plugins": [{"name": "demo"}]}
        )
        problems = check_marketplace(root)
        self.assertTrue(any("needs `name` and `source`" in p for p in problems))

    def test_source_that_is_not_a_directory_is_reported(self):
        root = self.make_root()
        self.write_marketplace(
            root,
            {"name": "cat", "plugins": [{"name": "demo", "source": "./nope"}]},
        )
        problems = check_marketplace(root)
        self.assertTrue(any("is not a directory" in p for p in problems))

    def test_directory_name_mismatch_is_reported(self):
        root = self.make_root()
        self.make_valid_plugin(root, "actual-dir")
        self.write_marketplace(
            root,
            {
                "name": "cat",
                "plugins": [{"name": "demo", "source": "./actual-dir"}],
            },
        )
        problems = check_marketplace(root)
        self.assertTrue(any("directory name and plugin name must match" in p for p in problems))

    def test_valid_marketplace_and_plugin_pass(self):
        root = self.make_root()
        self.make_valid_plugin(root, "demo")
        self.write_marketplace(
            root, {"name": "cat", "plugins": [{"name": "demo", "source": "./demo"}]}
        )
        self.assertEqual(check_marketplace(root), [])


if __name__ == "__main__":
    unittest.main()
