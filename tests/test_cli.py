from paperscope.cli import build_parser


def test_fetch_venue_parses_required_family():
    args = build_parser().parse_args(["fetch", "venue", "--family", "iclr"])
    assert args.family == ["iclr"]
    assert args.refresh_policy == "none"  # default: acquisition only


def test_fetch_venue_accepts_multiple_families_and_years():
    args = build_parser().parse_args(
        ["fetch", "venue", "--family", "iclr", "neurips", "--years", "2025", "2026", "--papers", "10", "--seed", "7"]
    )
    assert args.family == ["iclr", "neurips"]
    assert args.years == ["2025", "2026"]
    assert args.papers == 10
    assert args.seed == 7


def test_fetch_venue_refresh_policy_flag():
    args = build_parser().parse_args(["fetch", "venue", "--family", "iclr", "--refresh-policy", "active"])
    assert args.refresh_policy == "active"


def test_fetch_venue_rejects_unknown_refresh_policy():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["fetch", "venue", "--family", "iclr", "--refresh-policy", "bogus"])


def test_fetch_forum_parses_url():
    args = build_parser().parse_args(["fetch", "forum", "--url", "https://openreview.net/forum?id=abc"])
    assert args.url == "https://openreview.net/forum?id=abc"


def test_migrate_parses_path():
    args = build_parser().parse_args(["migrate", "corpus_iclr.json"])
    assert args.legacy_corpus == "corpus_iclr.json"


def test_fetch_venue_requires_family():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["fetch", "venue"])


def test_stats_parses_corpus_and_output():
    args = build_parser().parse_args(["stats", "--corpus", "data/full/iclr.jsonl", "--output", "artifacts/statistics"])
    assert args.corpus == "data/full/iclr.jsonl"
    assert args.output == "artifacts/statistics"


def test_stats_requires_corpus():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["stats"])


def test_evidence_parses_corpus_output_seed():
    args = build_parser().parse_args(
        ["evidence", "--corpus", "data/full/iclr.jsonl", "--output", "artifacts/bundle.json", "--seed", "7"]
    )
    assert args.corpus == "data/full/iclr.jsonl"
    assert args.output == "artifacts/bundle.json"
    assert args.seed == 7
    assert args.max_items > 0 and args.per_bucket > 0  # defaults are populated


def test_evidence_default_seed():
    args = build_parser().parse_args(["evidence", "--corpus", "data/full/iclr.jsonl", "--output", "out.json"])
    assert args.seed == 42


def test_evidence_requires_corpus():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["evidence"])
