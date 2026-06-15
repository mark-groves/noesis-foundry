from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DistributionDocsTests(unittest.TestCase):
    def test_install_guide_documents_fresh_editable_smoke_path(self) -> None:
        guide = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")

        required_snippets = [
            "python -m pip install -e .",
            "noesis vault doctor examples/noesis-vault --json",
            "noesis vault validate examples/noesis-vault",
            "noesis-mcp --help",
            "bash scripts/smoke-install.sh",
            "examples/mcp/noesis-mcp.example.json",
        ]
        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, guide)

        self.assertIn("vault files are the source of truth", guide.lower())
        self.assertIn("replaceable adapters", guide.lower())
        self.assertIn("must not introduce a second schema", guide.lower())
        self.assertNotIn("PYTHONPATH=src python -m noesis vault doctor", guide)

    def test_mcp_client_example_is_valid_stdio_config(self) -> None:
        config_path = ROOT / "examples" / "mcp" / "noesis-mcp.example.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        server = config["mcpServers"]["noesis"]
        self.assertTrue(server["command"].endswith("/noesis-mcp"))
        self.assertEqual(len(server["args"]), 1)
        self.assertTrue(server["args"][0].endswith("/noesis-vault"))
        self.assertNotIn("PYTHONPATH", json.dumps(config))

    def test_smoke_script_uses_installed_console_scripts_without_pythonpath(self) -> None:
        script = (ROOT / "scripts" / "smoke-install.sh").read_text(encoding="utf-8")

        required_snippets = [
            'python" -m pip install -e "$ROOT"',
            "unset PYTHONPATH",
            'noesis" vault doctor "$EXAMPLE_VAULT" --json',
            'noesis" vault validate "$EXAMPLE_VAULT"',
            'noesis-mcp" --help',
        ]
        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, script)


if __name__ == "__main__":
    unittest.main()
