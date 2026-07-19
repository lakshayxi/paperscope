"""Regression coverage: offline commands must never touch OpenReview.

`validate-skill` (and, by the same code path in `cli.main`, every other offline command
-- stats/evidence/export-prompt/render/build-skill) must not construct an OpenReview
client, hit the network, or print the "[paperscope] auth mode: ..." line that only
fetch/discover commands need. See `cli.py`'s `needs_auth` subparser flag.
"""

from __future__ import annotations

import json
import socket

import openreview
import pytest

from paperscope import skill_builder as sb
from paperscope.cli import main


def _fail(*args, **kwargs):
    raise AssertionError("OpenReview client construction attempted by an offline command")


@pytest.fixture
def built_skill_path(tmp_path):
    """A minimal, real, validated skill directory built the same way
    tests/test_skill_builder.py does -- self-contained here so this regression test
    doesn't depend on any other test module's fixtures.
    """
    statistics_payload = {
        "schema_version": 1, "corpus_hash": "hashL", "generated_at": "t0", "stat_count": 2,
        "stats": [
            {"metric": "forum_count", "venue_family": "fam", "venue_year": "all", "value": 3,
             "sample_size": 3, "missing_count": 0, "corpus_hash": "hashL", "generated_at": "t0",
             "schema_version": 1, "observational": False, "note": None},
            {"metric": "decision_distribution", "venue_family": "fam", "venue_year": "all",
             "value": {"unknown": 3}, "sample_size": 3, "missing_count": 3, "corpus_hash": "hashL",
             "generated_at": "t0", "schema_version": 1, "observational": False, "note": None},
        ],
    }
    evidence_payload = {
        "schema_version": 1, "corpus_hash": "hashL", "bundle_hash": "bhL", "generated_at": "t0",
        "seed": 42, "count": 0, "items": [],
    }
    claims_payload = {"claims": [
        {"claim_id": "c1", "section": "score_calibration", "claim_type": "insufficient_evidence",
         "text": "No data yet.", "evidence_ids": [], "statistic_refs": [], "year_scope": [],
         "support_level": "none", "limitations": ["nothing to report"]},
    ]}

    sp = tmp_path / "statistics.json"
    ep = tmp_path / "evidence.json"
    cp = tmp_path / "claims.json"
    sp.write_text(json.dumps(statistics_payload))
    ep.write_text(json.dumps(evidence_payload))
    cp.write_text(json.dumps(claims_payload))

    out = tmp_path / "skill"
    sb.build_skill(claims_path=cp, statistics_path=sp, evidence_path=ep, output_dir=out)
    return out


def test_validate_skill_cli_never_constructs_openreview_client(built_skill_path, monkeypatch, capsys):
    monkeypatch.setattr(openreview, "Client", _fail)
    monkeypatch.setattr(openreview.api, "OpenReviewClient", _fail)

    main(["validate-skill", "--path", str(built_skill_path)])

    captured = capsys.readouterr()
    assert "auth mode" not in captured.out
    assert "auth mode" not in captured.err


def test_validate_skill_cli_makes_no_network_call(built_skill_path, monkeypatch):
    monkeypatch.setattr(socket, "socket", _fail)
    main(["validate-skill", "--path", str(built_skill_path)])


def test_validate_skill_cli_prints_no_auth_mode_message(built_skill_path, capsys):
    main(["validate-skill", "--path", str(built_skill_path)])
    captured = capsys.readouterr()
    assert "[paperscope] auth mode" not in captured.err
    assert "[paperscope] auth mode" not in captured.out


def test_validate_skill_cli_never_imports_openreview_client_module(built_skill_path, monkeypatch):
    # Belt-and-suspenders: even though sys.modules can already contain
    # paperscope.openreview_client from earlier tests in this session, the parsed args
    # for validate-skill must never carry needs_auth -- that's the actual gate `main`
    # uses to decide whether to import it or resolve credentials at all.
    from paperscope.cli import build_parser

    args = build_parser().parse_args(["validate-skill", "--path", str(built_skill_path)])
    assert getattr(args, "needs_auth", False) is False


@pytest.mark.parametrize("argv", [
    ["stats", "--corpus", "unused.jsonl"],
    ["evidence", "--corpus", "unused.jsonl"],
    ["export-prompt", "--statistics", "a.json", "--evidence", "b.json"],
    ["render", "--claims", "a.json", "--statistics", "b.json", "--evidence", "c.json"],
    ["build-skill", "--claims", "a.json", "--statistics", "b.json", "--evidence", "c.json", "--output", "out"],
    ["validate-skill", "--path", "somewhere"],
])
def test_offline_commands_never_set_needs_auth(argv):
    from paperscope.cli import build_parser

    args = build_parser().parse_args(argv)
    assert getattr(args, "needs_auth", False) is False


@pytest.mark.parametrize("argv", [
    ["fetch", "venue", "--family", "iclr"],
    ["fetch", "forum", "--url", "https://openreview.net/forum?id=abc"],
    ["discover", "some.venue/Conference"],
])
def test_fetch_and_discover_commands_do_set_needs_auth(argv):
    from paperscope.cli import build_parser

    args = build_parser().parse_args(argv)
    assert getattr(args, "needs_auth", False) is True
