import copy
import json
import sys

import pytest

from paperscope import evidence as evidence_mod
from paperscope import generation as gen
from paperscope import statistics as statistics_mod
from paperscope import storage
from tests.conftest import build_synthetic_forum_records


def _synthetic_payloads():
    """Two-year synthetic fixture (fam/2024, fam/2025) -- lets 'unsupported venue/year
    scope' (year unknown anywhere) be tested distinctly from 'exceeds evidence scope'
    (year known globally, but not covered by *this claim's* own citations).
    """
    statistics_payload = {
        "schema_version": 1,
        "corpus_hash": "hash1",
        "generated_at": "t0",
        "stat_count": 4,
        "stats": [
            {
                "metric": "forum_count", "venue_family": "fam", "venue_year": 2024, "value": 5,
                "sample_size": 5, "missing_count": 0, "corpus_hash": "hash1", "generated_at": "t0",
                "schema_version": 1, "observational": False, "note": None,
            },
            {
                "metric": "forum_count", "venue_family": "fam", "venue_year": 2025, "value": 3,
                "sample_size": 3, "missing_count": 0, "corpus_hash": "hash1", "generated_at": "t0",
                "schema_version": 1, "observational": False, "note": None,
            },
            {
                "metric": "forum_count", "venue_family": "fam", "venue_year": "all", "value": 8,
                "sample_size": 8, "missing_count": 0, "corpus_hash": "hash1", "generated_at": "t0",
                "schema_version": 1, "observational": False, "note": None,
            },
            {
                "metric": "paper_mean_rating", "venue_family": "fam", "venue_year": 2024,
                "value": {"count": 5, "mean": 5.0, "stdev": 1.0, "median": 5.0, "min": 3.0, "max": 7.0},
                "sample_size": 5, "missing_count": 0, "corpus_hash": "hash1", "generated_at": "t0",
                "schema_version": 1, "observational": False, "note": None,
            },
        ],
    }
    evidence_payload = {
        "schema_version": 1,
        "corpus_hash": "hash1",
        "bundle_hash": "bh1",
        "generated_at": "t0",
        "seed": 42,
        "count": 1,
        "items": [
            {
                "evidence_id": "ev1", "venue_family": "fam", "venue_year": 2024,
                "forum_id": "f1", "note_id": "n1", "source_url": "https://openreview.net/forum?id=f1",
                "rating_designation": "initial", "rating_value": 4.0, "decision": "unknown",
                "content_hash": "ch1", "excerpt_text": "The paper lacks sufficient baselines for comparison.",
                "excerpt_length": 53, "corpus_hash": "hash1", "schema_version": 1, "strata": {},
            },
        ],
    }
    return statistics_payload, evidence_payload


def _base_claim(**overrides):
    claim = {
        "claim_id": "c1", "section": "score_calibration", "claim_type": "deterministic_fact",
        "text": "The mean rating is 5.0.", "evidence_ids": [], "statistic_refs": ["fam/2024/paper_mean_rating.mean"],
        "year_scope": [2024], "support_level": "strong", "limitations": ["small sample"],
    }
    claim.update(overrides)
    return claim


def _expect_error(statistics_payload, evidence_payload, claim, needle):
    with pytest.raises(gen.GenerationValidationError, match=needle):
        gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)


# --------------------------------------------------------------------------------------
# export-prompt / no-anthropic-dependency
# --------------------------------------------------------------------------------------


def test_export_prompt_works_without_anthropic_installed(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)  # simulates "not installed"
    statistics_payload, evidence_payload = _synthetic_payloads()
    (tmp_path / "statistics.json").write_text(json.dumps(statistics_payload))
    (tmp_path / "evidence.json").write_text(json.dumps(evidence_payload))

    manifest = gen.export_prompt(
        statistics_path=tmp_path / "statistics.json", evidence_path=tmp_path / "evidence.json",
        output_dir=tmp_path / "out",
    )
    assert (tmp_path / "out" / "prompt.md").exists()
    assert (tmp_path / "out" / "response_schema.json").exists()
    assert manifest["content"]["corpus_hash"] == "hash1"


def test_no_llm_import_on_export_validate_or_render(monkeypatch, tmp_path):
    monkeypatch.delitem(sys.modules, "anthropic", raising=False)
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim()
    gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)
    gen.render_markdown({"claims": [claim]}, statistics_payload, evidence_payload)
    (tmp_path / "statistics.json").write_text(json.dumps(statistics_payload))
    (tmp_path / "evidence.json").write_text(json.dumps(evidence_payload))
    gen.export_prompt(statistics_path=tmp_path / "statistics.json", evidence_path=tmp_path / "evidence.json", output_dir=tmp_path / "out")
    assert "anthropic" not in sys.modules


def test_export_prompt_rejects_mismatched_corpus_hashes(tmp_path):
    statistics_payload, evidence_payload = _synthetic_payloads()
    evidence_payload["corpus_hash"] = "different_hash"
    (tmp_path / "statistics.json").write_text(json.dumps(statistics_payload))
    (tmp_path / "evidence.json").write_text(json.dumps(evidence_payload))
    with pytest.raises(ValueError, match="different corpora"):
        gen.export_prompt(statistics_path=tmp_path / "statistics.json", evidence_path=tmp_path / "evidence.json", output_dir=tmp_path / "out")


def test_export_prompt_manifest_content_hash_stable_across_runs_ignoring_timestamp(tmp_path):
    statistics_payload, evidence_payload = _synthetic_payloads()
    (tmp_path / "statistics.json").write_text(json.dumps(statistics_payload))
    (tmp_path / "evidence.json").write_text(json.dumps(evidence_payload))

    m1 = gen.export_prompt(statistics_path=tmp_path / "statistics.json", evidence_path=tmp_path / "evidence.json",
                            output_dir=tmp_path / "out1", generated_at="2026-01-01T00:00:00Z")
    m2 = gen.export_prompt(statistics_path=tmp_path / "statistics.json", evidence_path=tmp_path / "evidence.json",
                            output_dir=tmp_path / "out2", generated_at="2026-06-06T00:00:00Z")
    assert m1["content_hash"] == m2["content_hash"]
    assert m1["generated_at"] != m2["generated_at"]


# --------------------------------------------------------------------------------------
# valid claims acceptance
# --------------------------------------------------------------------------------------


def test_valid_claim_accepted():
    statistics_payload, evidence_payload = _synthetic_payloads()
    gen.validate_claims({"claims": [_base_claim()]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)


def test_valid_evidence_excerpt_claim_accepted():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(
        claim_type="evidence_excerpt", statistic_refs=[], text="lacks sufficient baselines",
        evidence_ids=["ev1"], support_level="single_instance",
    )
    gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)


def test_valid_insufficient_evidence_claim_accepted():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(
        claim_type="insufficient_evidence", statistic_refs=[], text="Not enough data to support this.",
        year_scope=[], support_level="none",
    )
    gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)


def test_aggregate_all_scope_statistic_ref_covers_every_known_year():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(statistic_refs=["fam/all/forum_count"], year_scope=[2024, 2025], text="8 forums total.")
    gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)


# --------------------------------------------------------------------------------------
# adversarial validation
# --------------------------------------------------------------------------------------


def test_rejects_nonexistent_evidence_id():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(claim_type="evidence_excerpt", statistic_refs=[], text="x", evidence_ids=["ev_fake"])
    _expect_error(statistics_payload, evidence_payload, claim, "not found in evidence bundle")


def test_rejects_nonexistent_statistic_ref():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(statistic_refs=["fam/2024/does_not_exist"])
    _expect_error(statistics_payload, evidence_payload, claim, "does not resolve")


def test_rejects_invented_quotation():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(
        claim_type="evidence_excerpt", statistic_refs=[], evidence_ids=["ev1"],
        text="this exact sentence was never written by any reviewer",
    )
    _expect_error(statistics_payload, evidence_payload, claim, "not a verbatim excerpt")


def test_rejects_numeric_claim_without_statistic_refs():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(statistic_refs=[])
    _expect_error(statistics_payload, evidence_payload, claim, "no statistic_refs")


def test_rejects_evidence_excerpt_claim_without_evidence_ids():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(claim_type="evidence_excerpt", statistic_refs=[], text="no evidence cited")
    _expect_error(statistics_payload, evidence_payload, claim, "no evidence_ids")


def test_rejects_duplicate_claim_ids():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim()
    with pytest.raises(gen.GenerationValidationError, match="duplicate claim_id"):
        gen.validate_claims(
            {"claims": [claim, copy.deepcopy(claim)]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload
        )


def test_rejects_unsupported_year_scope():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(year_scope=[1999])
    _expect_error(statistics_payload, evidence_payload, claim, "unsupported venue/year scope")


def test_rejects_claim_exceeding_its_own_evidence_scope():
    # 2025 is a real, known year in the corpus -- but this claim only cites a 2024 stat,
    # so claiming year_scope [2024, 2025] over-reaches beyond what it actually cites.
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(year_scope=[2024, 2025])
    _expect_error(statistics_payload, evidence_payload, claim, "exceeds its evidence scope")


def test_rejects_missing_limitations():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(limitations=[])
    _expect_error(statistics_payload, evidence_payload, claim, "missing limitations")


def test_rejects_missing_support_level():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(support_level="")
    _expect_error(statistics_payload, evidence_payload, claim, "support_level")


def test_rejects_unrecognized_section():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(section="not_a_real_section")
    _expect_error(statistics_payload, evidence_payload, claim, "unrecognized section")


def test_rejects_unrecognized_claim_type():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(claim_type="not_a_real_type")
    _expect_error(statistics_payload, evidence_payload, claim, "unrecognized claim_type")


def test_reports_every_violation_not_just_first():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(limitations=[], support_level="bogus")
    try:
        gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)
        raise AssertionError("expected GenerationValidationError")
    except gen.GenerationValidationError as e:
        msg = str(e)
        assert "missing limitations" in msg
        assert "support_level" in msg


# --------------------------------------------------------------------------------------
# deterministic rendering / provenance
# --------------------------------------------------------------------------------------


def test_render_markdown_is_deterministic_and_order_independent():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim_a = _base_claim(claim_id="a")
    claim_b = _base_claim(claim_id="b", section="reject_signals", claim_type="evidence_excerpt", statistic_refs=[],
                           evidence_ids=["ev1"], text="lacks sufficient baselines", support_level="single_instance")
    payload = {"claims": [claim_a, claim_b]}
    payload_reversed = {"claims": [claim_b, claim_a]}

    md1 = gen.render_markdown(payload, statistics_payload, evidence_payload)
    md2 = gen.render_markdown(payload, statistics_payload, evidence_payload)
    md3 = gen.render_markdown(payload_reversed, statistics_payload, evidence_payload)
    assert md1 == md2 == md3


def test_render_groups_by_section():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim_a = _base_claim(claim_id="a", section="score_calibration")
    claim_b = _base_claim(claim_id="b", section="hidden_criteria")
    md = gen.render_markdown({"claims": [claim_a, claim_b]}, statistics_payload, evidence_payload)
    assert "## Score Calibration" in md
    assert "## Hidden Criteria" in md
    assert md.index("## Score Calibration") < md.index("## Hidden Criteria")


def test_render_shows_evidence_provenance_forum_note_url():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(claim_type="evidence_excerpt", statistic_refs=[], evidence_ids=["ev1"],
                         text="lacks sufficient baselines", support_level="single_instance")
    md = gen.render_markdown({"claims": [claim]}, statistics_payload, evidence_payload)
    assert "forum `f1`" in md
    assert "note `n1`" in md
    assert "https://openreview.net/forum?id=f1" in md


def test_render_preserves_support_level_and_limitations():
    statistics_payload, evidence_payload = _synthetic_payloads()
    claim = _base_claim(support_level="strong", limitations=["a specific stated caveat"])
    md = gen.render_markdown({"claims": [claim]}, statistics_payload, evidence_payload)
    assert "**Support level:** strong" in md
    assert "a specific stated caveat" in md


def test_render_never_silently_drops_invalid_claims():
    statistics_payload, evidence_payload = _synthetic_payloads()
    bad_claim = _base_claim(section="not_a_real_section")
    with pytest.raises(gen.GenerationValidationError):
        gen.render_markdown({"claims": [bad_claim]}, statistics_payload, evidence_payload)


def test_render_distinguishes_claim_types():
    statistics_payload, evidence_payload = _synthetic_payloads()
    fact = _base_claim(claim_id="a")
    excerpt = _base_claim(claim_id="b", section="reject_signals", claim_type="evidence_excerpt", statistic_refs=[],
                           evidence_ids=["ev1"], text="lacks sufficient baselines", support_level="single_instance")
    interp = _base_claim(claim_id="c", section="hidden_criteria", claim_type="llm_interpretation", statistic_refs=[],
                          text="Reviewers seem to weigh novelty heavily.", support_level="limited")
    md = gen.render_markdown({"claims": [fact, excerpt, interp]}, statistics_payload, evidence_payload)
    assert "Deterministic fact" in md
    assert "Evidence excerpt" in md
    assert "Model interpretation" in md


# --------------------------------------------------------------------------------------
# malformed provider output
# --------------------------------------------------------------------------------------


def test_parse_provider_response_rejects_non_json():
    with pytest.raises(gen.GenerationValidationError, match="not valid JSON"):
        gen.parse_provider_response("this is not json")


def test_parse_provider_response_rejects_missing_claims_key():
    with pytest.raises(gen.GenerationValidationError, match="missing a top-level 'claims'"):
        gen.parse_provider_response('{"foo": 1}')


def test_parse_provider_response_rejects_non_list_claims():
    with pytest.raises(gen.GenerationValidationError, match="must be a list"):
        gen.parse_provider_response('{"claims": "nope"}')


def test_parse_provider_response_strips_code_fence():
    result = gen.parse_provider_response('```json\n{"claims": []}\n```')
    assert result == {"claims": []}


def test_run_provider_generation_rejects_unknown_provider(tmp_path):
    from paperscope import llm_provider

    with pytest.raises(ValueError, match="unsupported provider"):
        llm_provider.run_provider_generation(prompt_dir=tmp_path, provider="openai", model="gpt-x")


# --------------------------------------------------------------------------------------
# smoke test against the real, already-fetched ICLR corpus
# --------------------------------------------------------------------------------------


def test_smoke_export_and_validate_against_synthetic_corpus(tmp_path):
    records = build_synthetic_forum_records()
    corpus_hash = storage.corpus_hash(records)
    stats = statistics_mod.compute_all_statistics(records, corpus_hash=corpus_hash, generated_at="t0")
    statistics_payload = json.loads(json.dumps({
        "schema_version": 1, "corpus_hash": corpus_hash, "generated_at": "t0",
        "stat_count": len(stats), "stats": [s.to_dict() for s in stats],
    }))
    items = evidence_mod.select_evidence(records, seed=42, corpus_hash=corpus_hash)
    evidence_payload = json.loads(json.dumps({
        "schema_version": 1, "corpus_hash": corpus_hash, "bundle_hash": "bh", "generated_at": "t0",
        "seed": 42, "count": len(items), "items": [i.to_dict() for i in items],
    }))

    (tmp_path / "statistics.json").write_text(json.dumps(statistics_payload))
    (tmp_path / "evidence.json").write_text(json.dumps(evidence_payload))
    manifest = gen.export_prompt(
        statistics_path=tmp_path / "statistics.json", evidence_path=tmp_path / "evidence.json", output_dir=tmp_path / "out"
    )
    assert manifest["content"]["corpus_hash"] == corpus_hash

    first_item = evidence_payload["items"][0]
    claim = _base_claim(
        claim_type="evidence_excerpt", statistic_refs=[], evidence_ids=[first_item["evidence_id"]],
        text=first_item["excerpt_text"][:30], year_scope=[first_item["venue_year"]], support_level="single_instance",
    )
    gen.validate_claims({"claims": [claim]}, statistics_payload=statistics_payload, evidence_payload=evidence_payload)
    md = gen.render_markdown({"claims": [claim]}, statistics_payload, evidence_payload)
    assert first_item["forum_id"] in md
