"""Regression test for expl.py bug #1: anthropic must not be a hard dependency of the
fetch-only path. Phase 3 will add `anthropic` as an optional import scoped to a
generation module -- nothing in the current fetch/CLI path should import it.
"""

import ast
import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src" / "paperscope"


def _module_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_no_paperscope_module_imports_anthropic():
    offenders = []
    for py_file in SRC_DIR.glob("*.py"):
        if "anthropic" in _module_level_imports(py_file):
            offenders.append(py_file.name)
    assert offenders == [], f"anthropic imported at module level in: {offenders}"


def test_importing_cli_does_not_pull_in_anthropic():
    sys.modules.pop("anthropic", None)
    import paperscope.cli  # noqa: F401

    assert "anthropic" not in sys.modules
