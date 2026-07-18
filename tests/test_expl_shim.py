"""Tests for expl.py's explicit legacy-command translation (not a blind passthrough)."""

import importlib.util
import sys
from pathlib import Path

_EXPL_PATH = Path(__file__).parent.parent / "expl.py"
_spec = importlib.util.spec_from_file_location("expl_shim", _EXPL_PATH)
expl_shim = importlib.util.module_from_spec(_spec)
sys.modules["expl_shim"] = expl_shim
_spec.loader.exec_module(expl_shim)


def test_bulk_translates_venues_to_family():
    result = expl_shim.translate(["bulk", "--venues", "iclr", "--years", "2026", "--per-venue", "20"])
    assert result == ["fetch", "venue", "--family", "iclr", "--years", "2026", "--papers", "20"]


def test_bulk_translates_multiple_venues():
    result = expl_shim.translate(["bulk", "--venues", "iclr", "neurips", "--per-venue", "5"])
    assert result == ["fetch", "venue", "--family", "iclr", "neurips", "--papers", "5"]


def test_bulk_drops_compress_and_output_with_warning(capsys):
    result = expl_shim.translate(["bulk", "--venues", "iclr", "--compress", "--output", "out.json"])
    assert result == ["fetch", "venue", "--family", "iclr"]
    err = capsys.readouterr().err
    assert "--compress" in err
    assert "--output" in err


def test_bulk_drops_force_with_warning(capsys):
    result = expl_shim.translate(["bulk", "--venues", "iclr", "--force"])
    assert result == ["fetch", "venue", "--family", "iclr"]
    assert "--force" in capsys.readouterr().err


def test_forum_translates_url():
    result = expl_shim.translate(["forum", "--url", "https://openreview.net/forum?id=abc"])
    assert result == ["fetch", "forum", "--url", "https://openreview.net/forum?id=abc"]


def test_forum_drops_save_with_warning(capsys):
    result = expl_shim.translate(["forum", "--url", "https://x", "--save"])
    assert result == ["fetch", "forum", "--url", "https://x"]
    assert "--save" in capsys.readouterr().err


def test_analyze_not_available(capsys):
    result = expl_shim.translate(["analyze", "--corpus", "corpus.json"])
    assert result is None
    assert "not available" in capsys.readouterr().err


def test_skill_not_available(capsys):
    result = expl_shim.translate(["skill"])
    assert result is None


def test_all_not_available(capsys):
    result = expl_shim.translate(["all"])
    assert result is None


def test_unknown_command_returns_none():
    assert expl_shim.translate(["frobnicate"]) is None


def test_empty_argv_returns_none():
    assert expl_shim.translate([]) is None
