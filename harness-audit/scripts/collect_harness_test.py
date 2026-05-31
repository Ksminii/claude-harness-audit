#!/usr/bin/env python3
"""Tests for collect_harness.py — frontmatter parsing, vendored classification,
duplicate detection, and skill hygiene metrics.

Builds a throwaway fake harness in a temp dir, runs the collector as a
subprocess, and asserts on the emitted JSON. Run directly:

    python3 collect_harness_test.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "collect_harness.py"

# Direct-import the pure helpers too.
sys.path.insert(0, str(HERE))
import collect_harness as ch  # noqa: E402


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_skill(skills_dir: Path, dirname: str, frontmatter: str, body: str = "Body.\n", extra_files=None):
    write(skills_dir / dirname / "SKILL.md", "---\n%s\n---\n%s" % (frontmatter, body))
    for fname in (extra_files or []):
        write(skills_dir / dirname / fname, "x")


class FrontmatterTests(unittest.TestCase):
    def test_block_scalar_description(self):
        text = "---\nname: foo\ndescription: |\n  Line one.\n  Use when bar.\n---\nBody"
        fm, body = ch.parse_frontmatter(text)
        self.assertEqual(fm["name"], "foo")
        self.assertIn("Use when bar.", fm["description"])
        self.assertEqual(body.strip(), "Body")

    def test_inline_value(self):
        fm, _ = ch.parse_frontmatter("---\nname: bar\ndescription: A thing.\n---\n")
        self.assertEqual(fm["name"], "bar")
        self.assertEqual(fm["description"], "A thing.")

    def test_no_frontmatter(self):
        fm, body = ch.parse_frontmatter("# Just a heading\n")
        self.assertIsNone(fm)


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.gdir = root / "global"
        cls.pdir = root / "project"
        skills = cls.gdir / "skills"

        # User-authored skill: minimal frontmatter, has a trigger.
        make_skill(skills, "good", "name: good\ndescription: Does X. Use when the user asks for X.")
        # Vendored: preamble-tier marker + long body.
        make_skill(
            skills, "vend", "name: vend\nversion: 1.0.0\npreamble-tier: 2\ndescription: Vendored. (gstack)",
            body="\n".join("line %d" % i for i in range(600)),
        )
        # No-trigger skill.
        make_skill(skills, "notrigger", "name: notrigger\ndescription: Purely a capability statement.")
        # Name mismatch + duplicate name with another dir.
        make_skill(skills, "dir-a", "name: shared\ndescription: A. Use when A.")
        make_skill(skills, "dir-b", "name: shared\ndescription: B. Use when B.")
        # When-to-use in body + extraneous file.
        make_skill(
            skills, "bodywhen", "name: bodywhen\ndescription: Y. Use when Y.",
            body="## When to use\nLater.\n", extra_files=["README.md"],
        )

        write(cls.gdir / "CLAUDE.md", "Global rules.\n")
        write(cls.gdir / "settings.json", json.dumps({
            "permissions": {"defaultMode": "auto"},
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},
            "enabledPlugins": {"missing@x": True},
        }))
        cls.pdir.mkdir(parents=True, exist_ok=True)

        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--global-dir", str(cls.gdir), "--project-dir", str(cls.pdir)],
            capture_output=True, text=True, check=True,
        )
        cls.snap = json.loads(out.stdout)
        cls.by_dir = {s["name_dir"]: s for s in cls.snap["skills"]["global"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_vendored_classification(self):
        self.assertFalse(self.by_dir["good"]["vendored"])
        self.assertTrue(self.by_dir["vend"]["vendored"])
        self.assertIn("preamble-tier", self.by_dir["vend"]["vendored_signals"])

    def test_trigger_detection(self):
        self.assertTrue(self.by_dir["good"]["description_has_trigger"])
        self.assertFalse(self.by_dir["notrigger"]["description_has_trigger"])

    def test_long_body(self):
        self.assertTrue(self.by_dir["vend"]["over_500_lines"])
        self.assertFalse(self.by_dir["good"]["over_500_lines"])

    def test_name_mismatch(self):
        self.assertTrue(self.by_dir["dir-a"].get("name_mismatch"))

    def test_duplicate_names(self):
        dups = self.snap["duplicate_skill_names"]
        self.assertIn("shared", dups)
        self.assertEqual(len(dups["shared"]), 2)

    def test_when_to_use_in_body_and_extraneous(self):
        self.assertTrue(self.by_dir["bodywhen"]["body_has_when_to_use_section"])
        self.assertIn("README.md", self.by_dir["bodywhen"]["extraneous_files"])

    def test_plugin_enabled_not_installed(self):
        self.assertIn("missing@x", self.snap["plugins"]["enabled_not_installed"])

    def test_settings_hooks_summarized(self):
        hooks = self.snap["settings"]["global"]["hooks"]
        self.assertIn("Stop", hooks)
        self.assertEqual(hooks["Stop"][0]["commands"], ["echo hi"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
