from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


class NoesisMcpStdioSmokeTests(unittest.TestCase):
    def test_stdio_entrypoint_registers_tools_and_invokes_core_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shim_root = tmp_path / "shim"
            record_path = tmp_path / "mcp-smoke.json"
            self._write_fastmcp_shim(shim_root)

            env = os.environ.copy()
            env["NOESIS_MCP_SMOKE_RECORD"] = str(record_path)
            env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(shim_root)])

            result = subprocess.run(
                [sys.executable, "-m", "noesis.mcp_server", str(EXAMPLE_VAULT)],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["server_name"], "Noesis Foundry")
            self.assertEqual(record["run_kwargs"], {"transport": "stdio"})
            self.assertIn("noesis_lint_vault", record["tools"])
            self.assertIn("noesis_build_context", record["tools"])
            self.assertIn("noesis://vault/summary", record["resources"])
            self.assertTrue(record["lint"]["ok"], record["lint"])
            self.assertEqual(record["lint"]["issue_count"], 0)
            self.assertTrue(record["summary"]["ok"], record["summary"])
            self.assertGreater(record["summary"]["note_count"], 0)
            self.assertTrue(record["context"]["ok"], record["context"])
            self.assertEqual(record["context"]["scope"], "agent-memory")
            self.assertIn("reviewed-knowledge-agent-memory-dogfood", record["context"]["content"])
            self.assertNotIn("stale-agent-memory-global-summary", record["context"]["content"])

    @staticmethod
    def _write_fastmcp_shim(root: Path) -> None:
        package = root / "mcp" / "server"
        package.mkdir(parents=True)
        (root / "mcp" / "__init__.py").write_text("", encoding="utf-8")
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "fastmcp.py").write_text(
            textwrap.dedent(
                """
                from __future__ import annotations

                import json
                import os


                class FastMCP:
                    def __init__(self, name: str, **kwargs: object) -> None:
                        self.name = name
                        self.kwargs = kwargs
                        self.tools = {}
                        self.resources = {}

                    def tool(self):
                        def register(function):
                            self.tools[function.__name__] = function
                            return function

                        return register

                    def resource(self, uri: str):
                        def register(function):
                            self.resources[uri] = function
                            return function

                        return register

                    def run(self, **kwargs: object) -> None:
                        lint = self.tools["noesis_lint_vault"]()
                        context = self.tools["noesis_build_context"](
                            scope="agent-memory",
                            purpose="stdio smoke test",
                        )
                        summary = self.resources["noesis://vault/summary"]()
                        payload = {
                            "server_name": self.name,
                            "server_kwargs": self.kwargs,
                            "run_kwargs": kwargs,
                            "tools": sorted(self.tools),
                            "resources": sorted(self.resources),
                            "lint": lint,
                            "context": context,
                            "summary": summary,
                        }
                        with open(os.environ["NOESIS_MCP_SMOKE_RECORD"], "w", encoding="utf-8") as handle:
                            json.dump(payload, handle, sort_keys=True)
                """
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
