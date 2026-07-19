"""Regression test for expl.py bug #1: anthropic must not be a hard dependency of the
fetch-only path. Phase 3B added `anthropic` as an optional import, confined entirely to
`llm_provider.py` (see that module's docstring) -- nothing else in `paperscope`,
including `generation.py` itself, may reference it, even inside a function body.
"""

import ast
import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src" / "paperscope"
LLM_PROVIDER_MODULE = "llm_provider.py"


def _module_level_imports(path: Path) -> set[str]:
    """Only top-level (unindented) import statements -- a lazy, function-scoped import
    (see llm_provider.py's `run_provider_generation`) is intentionally allowed and must
    not trip this check; that's what `_all_imports` below is for.
    """
    tree = ast.parse(path.read_text())
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _all_imports(path: Path) -> set[str]:
    """Every import anywhere in the file, including nested inside function bodies."""
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_no_paperscope_module_imports_anthropic_at_module_level():
    offenders = []
    for py_file in SRC_DIR.glob("*.py"):
        if "anthropic" in _module_level_imports(py_file):
            offenders.append(py_file.name)
    assert offenders == [], f"anthropic imported at module level in: {offenders}"


def test_anthropic_is_confined_to_the_llm_provider_module():
    offenders = []
    for py_file in SRC_DIR.glob("*.py"):
        if py_file.name == LLM_PROVIDER_MODULE:
            continue
        if "anthropic" in _all_imports(py_file):
            offenders.append(py_file.name)
    assert offenders == [], f"anthropic referenced outside {LLM_PROVIDER_MODULE} in: {offenders}"


def test_importing_cli_does_not_pull_in_anthropic():
    sys.modules.pop("anthropic", None)
    import paperscope.cli  # noqa: F401

    assert "anthropic" not in sys.modules


def test_importing_generation_does_not_pull_in_anthropic():
    sys.modules.pop("anthropic", None)
    import paperscope.generation  # noqa: F401

    assert "anthropic" not in sys.modules


def test_importing_llm_provider_alone_does_not_pull_in_anthropic():
    """Importing the module is safe even without `anthropic` installed -- only calling
    `run_provider_generation` (which does the lazy `import anthropic`) requires it.
    """
    sys.modules.pop("anthropic", None)
    import paperscope.llm_provider  # noqa: F401

    assert "anthropic" not in sys.modules
