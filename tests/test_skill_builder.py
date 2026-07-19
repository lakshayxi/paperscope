from __future__ import annotations

import json
import sys

import pytest

from paperscope import evidence as evidence_mod
from paperscope import generation as generation_mod
from paperscope import skill_builder as sb
from paperscope import statistics as statistics_mod
from paperscope import storage
from paperscope import venue_resolution as vr
from tests.conftest import build_synthetic_forum_records

# --------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------


def _real_pipeline_payloads():
    """Runs the actual stats/evidence pipeline (statistics.py / evidence.py) against the
    synthetic corpus from conftest.py -- single family ("iclr"), two years -- so builder
    tests exercise the real data shapes those modules produce, not a hand-trimmed stand-in.
    """
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
    return statistics_payload, evidence_payload


def _claims_for(statistics_payload, evidence_payload):
    first_item = evidence_payload["items"][0]
    claims = {
        "claims": [
            {
                "claim_id": "score_mean", "section": "score_calibration", "claim_type": "deterministic_fact",
                "text": "The mean paper rating in this sample is nonzero.", "evidence_ids": [],
                "statistic_refs": ["iclr/all/paper_mean_rating.mean"], "year_scope": [],
                "support_level": "limited", "limitations": ["small synthetic sample"],
            },
            {
                "claim_id": "reject_excerpt", "section": "reject_signals", "claim_type": "evidence_excerpt",
                "text": first_item["excerpt_text"][:30], "evidence_ids": [first_item["evidence_id"]],
                "statistic_refs": [], "year_scope": [first_item["venue_year"]],
                "support_level": "single_instance", "limitations": ["one reviewer's assessment"],
            },
            {
                "claim_id": "rebuttal_no_data", "section": "rebuttal_effectiveness", "claim_type": "insufficient_evidence",
                "text": "No validated rebuttal-effectiveness pattern is supported by this sample.",
                "evidence_ids": [], "statistic_refs": [], "year_scope": [],
                "support_level": "none", "limitations": ["synthetic fixture has no rebuttal-tagged data"],
            },
        ]
    }
    generation_mod.validate_claims(claims, statistics_payload=statistics_payload, evidence_payload=evidence_payload)
    return claims


def _write_bundle(tmp_path, statistics_payload, evidence_payload, claims_payload, *, prefix=""):
    sp = tmp_path / f"{prefix}statistics.json"
    ep = tmp_path / f"{prefix}evidence.json"
    cp = tmp_path / f"{prefix}claims.json"
    sp.write_text(json.dumps(statistics_payload))
    ep.write_text(json.dumps(evidence_payload))
    cp.write_text(json.dumps(claims_payload))
    return sp, ep, cp


@pytest.fixture
def bundle(tmp_path):
    statistics_payload, evidence_payload = _real_pipeline_payloads()
    claims_payload = _claims_for(statistics_payload, evidence_payload)
    sp, ep, cp = _write_bundle(tmp_path, statistics_payload, evidence_payload, claims_payload)
    return {"statistics": sp, "evidence": ep, "claims": cp, "statistics_payload": statistics_payload,
            "evidence_payload": evidence_payload, "claims_payload": claims_payload}


# --------------------------------------------------------------------------------------
# build + validate happy path
# --------------------------------------------------------------------------------------


def test_build_produces_valid_skill(tmp_path, bundle):
    out = tmp_path / "skill"
    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)
    assert (out / "SKILL.md").exists()
    assert (out / "manifest.json").exists()
    assert (out / "references" / "iclr.md").exists()
    assert manifest["content"]["supported_venue_families"] == ["iclr"]

    report = sb.validate_skill(out)
    assert report.ok, report.violations


def test_build_is_deterministic_for_identical_inputs(tmp_path, bundle):
    out1 = tmp_path / "skill1"
    out2 = tmp_path / "skill2"
    m1 = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                         evidence_path=bundle["evidence"], output_dir=out1, generated_at="2026-01-01T00:00:00Z")
    m2 = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                         evidence_path=bundle["evidence"], output_dir=out2, generated_at="2099-06-06T00:00:00Z")
    assert m1["content"] == m2["content"]
    assert m1["content_hash"] == m2["content_hash"]
    assert m1["generated_at"] != m2["generated_at"]
    assert (out1 / "SKILL.md").read_text() == (out2 / "SKILL.md").read_text()
    assert (out1 / "references" / "iclr.md").read_text() == (out2 / "references" / "iclr.md").read_text()


def test_calibration_metadata_matches_statistics(tmp_path, bundle):
    out = tmp_path / "skill"
    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)
    entry = manifest["content"]["venues"]["iclr"]
    assert entry["years_covered"] == [2024, 2025]
    assert entry["forum_count"] == 12
    assert entry["review_count"] > 0


def test_limitations_and_support_levels_preserved_in_rendered_reference(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    text = (out / "references" / "iclr.md").read_text()
    assert "small synthetic sample" in text
    assert "**Support level:** limited" in text
    assert "**Support level:** single_instance" in text


def test_insufficient_evidence_claims_and_sections_preserved(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    text = (out / "references" / "iclr.md").read_text()
    # the explicit insufficient_evidence claim renders...
    assert "No validated rebuttal-effectiveness pattern is supported by this sample." in text
    # ...and sections with zero claims get an explicit insufficient-evidence placeholder,
    # not silence or a fabricated claim.
    assert "Insufficient evidence: no validated claim was generated" in text
    assert "## Hidden Criteria" in text


def test_no_decision_claim_beyond_what_decisions_resolved_supports(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    text = (out / "references" / "iclr.md").read_text()
    assert "accept/reject calibration claim" in text


# --------------------------------------------------------------------------------------
# fail-closed behavior
# --------------------------------------------------------------------------------------


def test_invalid_claims_rejected_before_build(tmp_path, bundle):
    bad_claims = json.loads(bundle["claims"].read_text())
    bad_claims["claims"][0]["section"] = "not_a_real_section"
    bad_path = tmp_path / "bad_claims.json"
    bad_path.write_text(json.dumps(bad_claims))

    out = tmp_path / "skill"
    with pytest.raises(generation_mod.GenerationValidationError):
        sb.build_skill(claims_path=bad_path, statistics_path=bundle["statistics"],
                        evidence_path=bundle["evidence"], output_dir=out)
    assert not out.exists()


def test_mismatched_corpus_hash_rejected(tmp_path, bundle):
    bad_evidence = json.loads(bundle["evidence"].read_text())
    bad_evidence["corpus_hash"] = "different-hash"
    bad_path = tmp_path / "bad_evidence.json"
    bad_path.write_text(json.dumps(bad_evidence))

    out = tmp_path / "skill"
    with pytest.raises(sb.SkillBuildError, match="different corpora"):
        sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                        evidence_path=bad_path, output_dir=out)
    assert not out.exists()


def test_wrong_schema_version_rejected(tmp_path, bundle):
    bad_stats = json.loads(bundle["statistics"].read_text())
    bad_stats["schema_version"] = 999
    bad_path = tmp_path / "bad_stats.json"
    bad_path.write_text(json.dumps(bad_stats))

    out = tmp_path / "skill"
    with pytest.raises(sb.SkillBuildError, match="schema_version"):
        sb.build_skill(claims_path=bundle["claims"], statistics_path=bad_path,
                        evidence_path=bundle["evidence"], output_dir=out)
    assert not out.exists()


def test_ambiguous_claim_attribution_rejected_in_multi_family_build(tmp_path):
    statistics_payload = {
        "schema_version": 1, "corpus_hash": "h1", "generated_at": "t0", "stat_count": 2,
        "stats": [
            {"metric": "forum_count", "venue_family": "fam_a", "venue_year": "all", "value": 3,
             "sample_size": 3, "missing_count": 0, "corpus_hash": "h1", "generated_at": "t0",
             "schema_version": 1, "observational": False, "note": None},
            {"metric": "forum_count", "venue_family": "fam_b", "venue_year": "all", "value": 3,
             "sample_size": 3, "missing_count": 0, "corpus_hash": "h1", "generated_at": "t0",
             "schema_version": 1, "observational": False, "note": None},
        ],
    }
    evidence_payload = {
        "schema_version": 1, "corpus_hash": "h1", "bundle_hash": "bh", "generated_at": "t0",
        "seed": 42, "count": 0, "items": [],
    }
    claims_payload = {"claims": [
        {"claim_id": "orphan", "section": "score_calibration", "claim_type": "insufficient_evidence",
         "text": "No data.", "evidence_ids": [], "statistic_refs": [], "year_scope": [],
         "support_level": "none", "limitations": ["no refs at all"]},
    ]}
    sp, ep, cp = _write_bundle(tmp_path, statistics_payload, evidence_payload, claims_payload)
    out = tmp_path / "skill"
    with pytest.raises(sb.SkillBuildError, match="ambiguous attribution"):
        sb.build_skill(claims_path=cp, statistics_path=sp, evidence_path=ep, output_dir=out)
    assert not out.exists()


# --------------------------------------------------------------------------------------
# validate_skill: missing / tampered / forbidden content
# --------------------------------------------------------------------------------------


def test_validate_detects_missing_reference_file(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    (out / "references" / "iclr.md").unlink()

    report = sb.validate_skill(out)
    assert not report.ok
    assert any("does not exist" in v for v in report.violations)


def test_validate_detects_tampered_reference_hash(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    ref_path = out / "references" / "iclr.md"
    ref_path.write_text(ref_path.read_text() + "\ntampered addition\n")

    report = sb.validate_skill(out)
    assert not report.ok
    assert any("hash mismatch" in v for v in report.violations)


def test_validate_detects_tampered_manifest_content_hash(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["content"]["claims_hash"] = "tampered"
    (out / "manifest.json").write_text(json.dumps(manifest))

    report = sb.validate_skill(out)
    assert not report.ok
    assert any("content_hash does not match" in v for v in report.violations)


def test_validate_detects_forbidden_overclaim_phrase(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    ref_path = out / "references" / "iclr.md"
    ref_path.write_text(ref_path.read_text() + "\nReviewers here have area-chair-level experience.\n")

    report = sb.validate_skill(out)
    assert not report.ok
    assert any("forbidden overclaim" in v for v in report.violations)


def test_old_iclr_fallback_text_absent_from_generated_skill_md(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    text = (out / "SKILL.md").read_text().lower()
    assert "apply iclr conventions as a neutral default" not in text
    assert "actual distribution of accepted" not in text
    assert "area-chair-level experience" not in text


def test_validate_detects_manifest_alias_collision(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["content"]["venues"]["iclr"]["aliases"] = ["iclr", "Collides"]
    manifest["content"]["venues"]["fake"] = {
        "reference": "references/iclr.md", "reference_hash": manifest["content"]["venues"]["iclr"]["reference_hash"],
        "aliases": ["Collides"], "years_covered": [], "forum_count": 1, "review_count": 1,
        "evidence_count": 0, "decisions_resolved": 0, "claim_count": 0, "preliminary": True,
    }
    manifest["content"]["supported_venue_families"] = sorted(manifest["content"]["venues"])
    (out / "manifest.json").write_text(json.dumps(manifest))

    report = sb.validate_skill(out)
    assert not report.ok
    assert any("alias collision" in v for v in report.violations)


def test_validate_rejects_manifest_pointing_into_legacy(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["content"]["venues"]["iclr"]["reference"] = "references/legacy/iclr.md"
    (out / "manifest.json").write_text(json.dumps(manifest))

    report = sb.validate_skill(out)
    assert not report.ok
    assert any("legacy" in v for v in report.violations)


# --------------------------------------------------------------------------------------
# legacy isolation
# --------------------------------------------------------------------------------------


def test_legacy_references_carried_forward_and_unreachable(tmp_path, bundle):
    out = tmp_path / "skill"
    legacy_dir = out / "references" / "legacy"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "old_iclr.md").write_text(
        "Archival, unverified. Mentions area-chair-level experience and the actual "
        "distribution of accepted/rejected papers -- kept only for historical continuity."
    )

    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)

    # carried forward unchanged...
    assert (legacy_dir / "old_iclr.md").exists()
    assert "area-chair-level experience" in (legacy_dir / "old_iclr.md").read_text()

    # ...but unreachable through normal venue selection: no manifest venue points there,
    # and the forbidden-phrase scan (which does flag non-legacy content) doesn't touch it.
    for entry in manifest["content"]["venues"].values():
        assert "legacy" not in entry["reference"]
    report = sb.validate_skill(out)
    assert report.ok, report.violations

    result = vr.resolve_venue("old_iclr", manifest["content"]["venues"])
    assert result.status == vr.STATUS_UNSUPPORTED


def test_skill_md_instructs_never_to_load_legacy(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    text = (out / "SKILL.md").read_text()
    assert "references/legacy/" in text
    assert "Never load anything from" in text


# --------------------------------------------------------------------------------------
# venue resolution wired through a real build
# --------------------------------------------------------------------------------------


def test_supported_venue_resolves_via_built_manifest(tmp_path, bundle):
    out = tmp_path / "skill"
    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)
    result = vr.resolve_venue("iclr", manifest["content"]["venues"])
    assert result.status == vr.STATUS_SUPPORTED
    assert result.reference == "references/iclr.md"


def test_known_alias_resolves_via_built_manifest(tmp_path, bundle):
    out = tmp_path / "skill"
    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)
    result = vr.resolve_venue("International Conference on Learning Representations", manifest["content"]["venues"])
    assert result.status == vr.STATUS_SUPPORTED
    assert result.family == "iclr"


def test_unsupported_venue_enters_generic_uncalibrated_and_never_resolves_to_iclr(tmp_path, bundle):
    out = tmp_path / "skill"
    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)
    venues = manifest["content"]["venues"]
    for query in ("NeurIPS", "ACL 2025", "some workshop nobody's heard of"):
        result = vr.resolve_venue(query, venues)
        assert result.status == vr.STATUS_UNSUPPORTED
        assert result.family != "iclr"
    assert sb.GENERIC_UNCALIBRATED in (out / "SKILL.md").read_text()


def test_only_manifest_listed_families_are_advertised(tmp_path, bundle):
    # The synthetic corpus is iclr-only -- ACL/AAAI/KDD/etc. must not appear anywhere,
    # even though skill_builder.KNOWN_VENUE_ALIASES has entries for them.
    out = tmp_path / "skill"
    manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                               evidence_path=bundle["evidence"], output_dir=out)
    assert manifest["content"]["supported_venue_families"] == ["iclr"]
    skill_md = (out / "SKILL.md").read_text().lower()
    for unsupported in ("acl", "aaai", "kdd"):
        assert unsupported not in skill_md


# --------------------------------------------------------------------------------------
# atomic build failure must not corrupt an existing valid skill
# --------------------------------------------------------------------------------------


def test_atomic_build_failure_does_not_corrupt_existing_valid_skill(tmp_path, bundle):
    out = tmp_path / "skill"
    good_manifest = sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                                    evidence_path=bundle["evidence"], output_dir=out)

    bad_claims = json.loads(bundle["claims"].read_text())
    bad_claims["claims"][0]["section"] = "not_a_real_section"
    bad_path = tmp_path / "bad_claims.json"
    bad_path.write_text(json.dumps(bad_claims))

    with pytest.raises(generation_mod.GenerationValidationError):
        sb.build_skill(claims_path=bad_path, statistics_path=bundle["statistics"],
                        evidence_path=bundle["evidence"], output_dir=out)

    manifest_after = json.loads((out / "manifest.json").read_text())
    assert manifest_after["content_hash"] == good_manifest["content_hash"]
    report = sb.validate_skill(out)
    assert report.ok, report.violations

    leftovers = list(tmp_path.glob("skill.tmp*")) + list(tmp_path.glob("skill.prev*"))
    assert leftovers == []


def test_atomic_self_validation_failure_does_not_write_output(tmp_path, bundle, monkeypatch):
    # Force the builder's own post-build self-validation to fail, simulating a bug that
    # produces an internally-inconsistent skill -- the swap must never happen.
    monkeypatch.setattr(sb, "validate_skill", lambda path: sb.SkillValidationReport(["forced failure"]))
    out = tmp_path / "skill"
    with pytest.raises(sb.SkillBuildError, match="forced failure"):
        sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                        evidence_path=bundle["evidence"], output_dir=out)
    assert not out.exists()


# --------------------------------------------------------------------------------------
# no anthropic import, no network
# --------------------------------------------------------------------------------------


def test_build_and_validate_work_without_anthropic_installed(tmp_path, bundle, monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    report = sb.validate_skill(out)
    assert report.ok, report.violations


def test_no_anthropic_module_imported_by_build_or_validate(tmp_path, bundle, monkeypatch):
    monkeypatch.delitem(sys.modules, "anthropic", raising=False)
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    sb.validate_skill(out)
    assert "anthropic" not in sys.modules


def test_build_and_validate_require_no_network(tmp_path, bundle, monkeypatch):
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted during build/validate")

    monkeypatch.setattr(socket, "socket", _blocked)
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    report = sb.validate_skill(out)
    assert report.ok, report.violations


# --------------------------------------------------------------------------------------
# frontmatter parsing
# --------------------------------------------------------------------------------------


def test_split_frontmatter_round_trips_generated_skill_md(tmp_path, bundle):
    out = tmp_path / "skill"
    sb.build_skill(claims_path=bundle["claims"], statistics_path=bundle["statistics"],
                    evidence_path=bundle["evidence"], output_dir=out)
    text = (out / "SKILL.md").read_text()
    frontmatter, body = sb.split_frontmatter(text)
    assert frontmatter["name"] == "paperscope-reviewer"
    assert "PaperScope" in body


def test_split_frontmatter_rejects_missing_block():
    frontmatter, body = sb.split_frontmatter("# No frontmatter here\n")
    assert frontmatter is None
