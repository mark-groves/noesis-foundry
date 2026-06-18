from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class SkillPackageTests(unittest.TestCase):
    def test_expected_skills_exist(self) -> None:
        expected = {
            "noesis-ingest",
            "noesis-claim-review",
            "noesis-context",
        }
        actual = {path.name for path in SKILLS.iterdir() if (path / "SKILL.md").exists()}
        self.assertEqual(actual, expected)

    def test_skill_frontmatter_is_portable_and_trigger_oriented(self) -> None:
        for skill_path in sorted(SKILLS.glob("*/SKILL.md")):
            with self.subTest(skill=skill_path.parent.name):
                frontmatter, body = self._read_skill(skill_path)

                self.assertEqual(frontmatter["name"], skill_path.parent.name)
                self.assertRegex(frontmatter["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                self.assertIn("description", frontmatter)
                self.assertLessEqual(len(frontmatter["description"]), 1024)
                self.assertIn("Use when", frontmatter["description"])
                self.assertLessEqual(set(frontmatter), {"name", "description", "license", "allowed-tools", "metadata"})

                self.assertIn("noesis vault validate", body)
                self.assertIn("PYTHONPATH=src python -m noesis vault validate", body)
                self.assertIn("portable Agent Skill", body)
                self.assertIn("Fallback", body)
                self.assertIn("Reviewability", body)
                self.assertIn("Concrete Example", body)
                self.assertIn("MCP", body)
                self.assertIn("README", body)
                self.assertNotIn("## Required Properties", body)

                concrete_example = body.split("## Concrete Example", 1)[1]
                self.assertIn("noesis ", concrete_example)
                self.assertNotIn("PYTHONPATH=src python -m noesis", concrete_example)

    def test_skill_readme_links_to_all_skills(self) -> None:
        readme = (SKILLS / "README.md").read_text(encoding="utf-8")
        for skill_name in ["noesis-ingest", "noesis-claim-review", "noesis-context"]:
            self.assertIn(f"./{skill_name}/SKILL.md", readme)

        self.assertIn("noesis vault validate examples/noesis-vault", readme)
        self.assertIn("From a source checkout without installation", readme)
        self.assertIn("PYTHONPATH=src python -m noesis", readme)

    @staticmethod
    def _read_skill(path: Path) -> tuple[dict[str, object], str]:
        content = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if match is None:
            raise AssertionError(f"{path} does not start with YAML frontmatter")
        frontmatter = yaml.safe_load(match.group(1))
        if not isinstance(frontmatter, dict):
            raise AssertionError(f"{path} frontmatter is not a mapping")
        return frontmatter, match.group(2)
