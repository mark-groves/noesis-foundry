from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from importlib import import_module
import io
import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


class ConsoleScriptSmokeTests(unittest.TestCase):
    def test_pyproject_console_script_targets_start(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["noesis"], "noesis.cli:main")
        self.assertEqual(scripts["noesis-mcp"], "noesis.mcp_server:main")

        noesis = load_script_target(scripts["noesis"])
        noesis_result = call_script(noesis, ["vault", "doctor", str(EXAMPLE_VAULT), "--json"])
        self.assertEqual(noesis_result.returncode, 0, noesis_result.stderr)
        payload = json.loads(noesis_result.stdout)
        self.assertEqual(payload["ready_for_cli_mcp"], True)
        self.assertEqual(payload["contract"]["version"], "1")

        noesis_mcp = load_script_target(scripts["noesis-mcp"])
        mcp_help = call_script(noesis_mcp, ["--help"])
        self.assertEqual(mcp_help.returncode, 0, mcp_help.stderr)
        self.assertIn("Default Noesis vault path", mcp_help.stdout)


class ScriptResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def load_script_target(spec: str) -> object:
    module_name, function_name = spec.split(":", 1)
    module = import_module(module_name)
    return getattr(module, function_name)


def call_script(target: object, argv: list[str]) -> ScriptResult:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            returncode = target(argv)  # type: ignore[misc]
        except SystemExit as exc:
            returncode = int(exc.code or 0)
    return ScriptResult(returncode, stdout.getvalue(), stderr.getvalue())
