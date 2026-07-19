from __future__ import annotations

import json
import socket
import sys

import openreview
import pytest

from paperscope import evaluation as ev
from paperscope import storage
from paperscope.config import NO_CALIBRATION
from paperscope.models import Decision, ForumRecord, Paper, Rating, Review

# --------------------------------------------------------------------------------------
# Synthetic fixtures. Deliberately covers every Decision.normalized value ("accept",
# "reject", "withdrawn", "desk_reject", "unknown") plus forums with zero ratings, since
# tests/conftest.py's build_synthetic_forum_records only covers accept/reject/unknown.
# --------------------------------------------------------------------------------------


def _review(note_id, rating=None, final_rating=None, text="A sufficiently long synthetic review body for testing."):
    review = Review(
        note_id=note_id,
        initial_rating=Rating(raw=str(rating), value=rating) if rating is not None else Rating(),
        final_rating=Rating(raw=str(final_rating), value=final_rating) if final_rating is not None else None,
        text=text,
    )
    review.content_hash = review.compute_hash()
    return review


def _forum(forum_id, *, family="fam", year=2025, decision="accept", reviews=None, title=None, abstract=None, responses=None):
    return ForumRecord(
        forum_id=forum_id,
        url=f"https://openreview.net/forum?id={forum_id}",
        venue_family=family,
        venue_id=f"{family}.org/{year}/Conference",
        venue_year=year,
        api_version="v2",
        paper=Paper(
            title=title if title is not None else f"Paper title for {forum_id}",
            abstract=abstract if abstract is not None else f"A short synthetic abstract for {forum_id}.",
        ),
        decision=Decision(raw_text=decision, normalized=decision),
        reviews=reviews or [],
        responses=responses or [],
    )


def _diverse_corpus() -> dict[str, ForumRecord]:
    forums = [
        _forum("e01", family="iclr", year=2025, decision="accept", reviews=[_review("e01_r1", 6.0), _review("e01_r2", 8.0)]),
        _forum("e02", family="iclr", year=2025, decision="reject", reviews=[_review("e02_r1", 3.0)]),
        _forum("e03", family="iclr", year=2024, decision="withdrawn", reviews=[_review("e03_r1", 5.0)]),
        _forum("e04", family="iclr", year=2024, decision="desk_reject", reviews=[]),
        _forum("e05", family="neurips", year=2025, decision="unknown", reviews=[_review("e05_r1", 4.0)]),
        _forum("e06", family="neurips", year=2025, decision="accept", reviews=[_review("e06_r1", 9.0, final_rating=7.0)]),
        _forum("e07", family="neurips", year=2024, decision="unknown", reviews=[]),  # no usable labels at all
        _forum("c01", family="iclr", year=2025, decision="accept", reviews=[_review("c01_r1", 7.0)]),
        _forum("c02", family="iclr", year=2025, decision="reject", reviews=[_review("c02_r1", 2.0)]),
    ]
    return {f.forum_id: f for f in forums}


@pytest.fixture
def diverse_corpus_path(tmp_path):
    records = _diverse_corpus()
    path = tmp_path / "corpus.jsonl"
    storage.save_full_corpus(path, records)
    return path


@pytest.fixture
def calibration_forums_path(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(["c01", "c02"]))
    return path


def _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path, out_name="dataset"):
    out_dir = tmp_path / out_name
    manifest = ev.prepare_eval(
        corpus_path=diverse_corpus_path,
        calibration_forums_path=calibration_forums_path,
        output_dir=out_dir,
        seed=42,
        generated_at="2026-01-01T00:00:00Z",
    )
    return out_dir, manifest


def _predictions_payload(system, eval_forum_ids, *, model_inputs_hash, calibration_hash, rating=5.0, decision="accept", prob=None):
    return {
        "run": {
            "run_id": f"{system}_run",
            "system": system,
            "model": "claude-x",
            "settings": {"temperature": 0},
            "input_hash": model_inputs_hash,
            "calibration_hash": calibration_hash,
            "created_at": "2026-01-01T00:00:00Z",
        },
        "predictions": [
            {
                "forum_id": fid,
                "rating_prediction": rating,
                "decision_prediction": decision,
                "accept_probability": prob,
                "reasoning_summary": "synthetic fixture",
            }
            for fid in eval_forum_ids
        ],
    }


# --------------------------------------------------------------------------------------
# prepare-eval: split, disjointness, exclusions, leakage
# --------------------------------------------------------------------------------------


def test_prepare_eval_deterministic_for_same_seed_and_inputs(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_a, _ = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path, out_name="a")
    out_b, _ = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path, out_name="b")
    assert (out_a / "model_inputs.jsonl").read_text() == (out_b / "model_inputs.jsonl").read_text()
    assert (out_a / "private_labels.jsonl").read_text() == (out_b / "private_labels.jsonl").read_text()
    assert json.loads((out_a / "evaluation_manifest.json").read_text()) == json.loads(
        (out_b / "evaluation_manifest.json").read_text()
    )


def test_calibration_and_evaluation_forums_are_disjoint(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = {json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()}
    calibration_ids = set(json.loads((calibration_forums_path).read_text()))
    assert eval_ids.isdisjoint(calibration_ids)
    assert "c01" not in eval_ids and "c02" not in eval_ids


def test_calibration_forum_overlap_is_excluded_with_reason(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, _ = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    split = json.loads((out_dir / "split_manifest.json").read_text())
    reasons = {e["forum_id"]: e["reason"] for e in split["exclusions"]}
    assert reasons["c01"] == "in_calibration_set"
    assert reasons["c02"] == "in_calibration_set"


def test_duplicate_calibration_forum_ids_are_deduplicated(tmp_path):
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(["a", "a", "b", "a"]))
    ids = ev.load_calibration_forum_ids(path)
    assert ids == {"a", "b"}


def test_load_calibration_forum_ids_accepts_evidence_bundle_shape(tmp_path):
    path = tmp_path / "cal.json"
    path.write_text(json.dumps({"items": [{"forum_id": "x1"}, {"forum_id": "x2"}, {"forum_id": "x1"}]}))
    assert ev.load_calibration_forum_ids(path) == {"x1", "x2"}


def test_empty_calibration_set_rejected(tmp_path):
    path = tmp_path / "cal.json"
    path.write_text(json.dumps([]))
    with pytest.raises(ev.EvaluationDatasetError):
        ev.load_calibration_forum_ids(path)


def test_calibration_hash_is_frozen_and_reproducible():
    ids_a = {"f1", "f2", "f3"}
    ids_b = {"f3", "f2", "f1"}  # same set, different construction order
    assert ev.freeze_calibration_hash(ids_a) == ev.freeze_calibration_hash(ids_b)

    different = {"f1", "f2"}
    assert ev.freeze_calibration_hash(ids_a) != ev.freeze_calibration_hash(different)


def test_split_manifest_records_calibration_hash_reproducibly_from_forum_ids(
    tmp_path, diverse_corpus_path, calibration_forums_path
):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    split = json.loads((out_dir / "split_manifest.json").read_text())
    recomputed = ev.freeze_calibration_hash(set(split["calibration_forum_ids"]))
    assert recomputed == split["calibration_hash"] == manifest["calibration_hash"]


def test_review_leakage_detected_when_abstract_contains_review_text():
    leaking_text = "This exact review sentence has been copy-pasted into the abstract by mistake here."
    records = {
        "leaky": _forum(
            "leaky",
            reviews=[_review("leaky_r1", 5.0, text=leaking_text)],
            abstract=f"Some intro. {leaking_text} Some outro.",
        )
    }
    model_inputs = [ev.build_model_input(records["leaky"])]
    errors = ev.check_no_review_leakage(records, model_inputs)
    assert errors and "leaky" in errors[0]


def test_review_leakage_free_corpus_passes(tmp_path, diverse_corpus_path, calibration_forums_path):
    # prepare_eval itself raises EvaluationDatasetError if leakage is detected -- reaching
    # this point at all is the assertion.
    _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)


def test_prepare_eval_raises_when_corpus_leaks_review_text(tmp_path, calibration_forums_path):
    leaking_text = "This exact rebuttal sentence has been copy-pasted into the title field by mistake here today."
    records = {
        "leaky": _forum("leaky", reviews=[_review("leaky_r1", 5.0)], title=leaking_text,
                         responses=[__import__("paperscope.models", fromlist=["Response"]).Response(note_id="leaky_resp", text=leaking_text)]),
    }
    corpus_path = tmp_path / "leaky_corpus.jsonl"
    storage.save_full_corpus(corpus_path, records)
    with pytest.raises(ev.EvaluationDatasetError):
        ev.prepare_eval(
            corpus_path=corpus_path, calibration_forums_path=calibration_forums_path,
            output_dir=tmp_path / "out", seed=42,
        )


# --------------------------------------------------------------------------------------
# separate task targets
# --------------------------------------------------------------------------------------


def test_initial_rating_target_uses_only_initial_ratings_never_final():
    record = _forum("f1", decision="accept", reviews=[_review("r1", rating=2.0, final_rating=9.0)])
    label = ev.build_private_label(record)
    assert label.initial_rating_target == 2.0
    assert label.initial_rating_eligible is True


def test_final_decision_target_never_derived_from_rating():
    # High rating, but decision is "reject" -- the label must follow decision, not rating.
    record = _forum("f1", decision="reject", reviews=[_review("r1", rating=9.5)])
    label = ev.build_private_label(record)
    assert label.final_decision_target == "reject"


def test_targets_for_the_two_tasks_are_independent_fields():
    record = _forum("f1", decision="withdrawn", reviews=[_review("r1", rating=7.0)])
    label = ev.build_private_label(record)
    # rating task is unaffected by the withdrawn decision...
    assert label.initial_rating_target == 7.0
    assert label.initial_rating_eligible is True
    # ...while the decision task is excluded, independently.
    assert label.final_decision_eligible is False
    assert label.final_decision_target is None


@pytest.mark.parametrize(
    "decision,expected_reason",
    [("withdrawn", "withdrawn"), ("desk_reject", "desk_reject"), ("unknown", "unresolved"), ("", "unresolved")],
)
def test_unresolved_decisions_excluded_from_final_decision_task(decision, expected_reason):
    record = _forum("f1", decision=decision, reviews=[_review("r1", rating=5.0)])
    label = ev.build_private_label(record)
    assert label.final_decision_eligible is False
    assert label.final_decision_target is None
    assert label.final_decision_excluded_reason == expected_reason


@pytest.mark.parametrize("decision", ["accept", "reject"])
def test_resolved_decisions_are_eligible(decision):
    record = _forum("f1", decision=decision, reviews=[_review("r1", rating=5.0)])
    label = ev.build_private_label(record)
    assert label.final_decision_eligible is True
    assert label.final_decision_target == decision
    assert label.final_decision_excluded_reason is None


def test_forum_with_no_ratings_and_no_resolved_decision_excluded_from_eval_set(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, _ = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    split = json.loads((out_dir / "split_manifest.json").read_text())
    reasons = {e["forum_id"]: e["reason"] for e in split["exclusions"]}
    assert reasons["e07"] == "no_usable_labels"


# --------------------------------------------------------------------------------------
# prediction schema validation
# --------------------------------------------------------------------------------------


def test_valid_prediction_schema_has_no_violations(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    payload = _predictions_payload(
        "generic", eval_ids, model_inputs_hash=manifest["model_inputs_hash"], calibration_hash=NO_CALIBRATION
    )
    assert ev.validate_prediction_schema(payload) == []


def test_prediction_schema_rejects_missing_run_fields():
    payload = {"run": {"system": "generic"}, "predictions": []}
    errors = ev.validate_prediction_schema(payload)
    assert any("run_id" in e for e in errors)
    assert any("model" in e for e in errors)


def test_prediction_schema_rejects_invalid_decision_value():
    payload = {
        "run": {"run_id": "r", "system": "generic", "model": "m", "settings": {}, "input_hash": "h", "calibration_hash": "none", "created_at": "t"},
        "predictions": [{"forum_id": "f1", "rating_prediction": 5.0, "decision_prediction": "maybe", "accept_probability": None}],
    }
    errors = ev.validate_prediction_schema(payload)
    assert any("decision_prediction" in e for e in errors)


def test_prediction_schema_rejects_non_numeric_rating():
    payload = {
        "run": {"run_id": "r", "system": "generic", "model": "m", "settings": {}, "input_hash": "h", "calibration_hash": "none", "created_at": "t"},
        "predictions": [{"forum_id": "f1", "rating_prediction": "high", "decision_prediction": None, "accept_probability": None}],
    }
    errors = ev.validate_prediction_schema(payload)
    assert any("rating_prediction" in e for e in errors)


def test_prediction_schema_rejects_out_of_range_probability():
    payload = {
        "run": {"run_id": "r", "system": "generic", "model": "m", "settings": {}, "input_hash": "h", "calibration_hash": "none", "created_at": "t"},
        "predictions": [{"forum_id": "f1", "rating_prediction": None, "decision_prediction": None, "accept_probability": 1.5}],
    }
    errors = ev.validate_prediction_schema(payload)
    assert any("accept_probability" in e for e in errors)


def test_prediction_schema_rejects_duplicate_forum_id():
    payload = {
        "run": {"run_id": "r", "system": "generic", "model": "m", "settings": {}, "input_hash": "h", "calibration_hash": "none", "created_at": "t"},
        "predictions": [
            {"forum_id": "f1", "rating_prediction": 5.0, "decision_prediction": None, "accept_probability": None},
            {"forum_id": "f1", "rating_prediction": 6.0, "decision_prediction": None, "accept_probability": None},
        ],
    }
    errors = ev.validate_prediction_schema(payload)
    assert any("duplicate forum_id" in e for e in errors)


def test_unknown_forum_id_in_predictions_is_rejected(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    payload = _predictions_payload(
        "generic", eval_ids + ["not_an_eval_forum"], model_inputs_hash=manifest["model_inputs_hash"], calibration_hash=NO_CALIBRATION
    )
    errors, missing = ev.validate_predictions_against_dataset(payload, set(eval_ids))
    assert errors and "not_an_eval_forum" in errors[0]
    assert missing == []


def test_missing_predictions_reported_not_rejected(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    partial_ids = eval_ids[:-1]
    payload = _predictions_payload(
        "generic", partial_ids, model_inputs_hash=manifest["model_inputs_hash"], calibration_hash=NO_CALIBRATION
    )
    errors, missing = ev.validate_predictions_against_dataset(payload, set(eval_ids))
    assert errors == []
    assert missing == [eval_ids[-1]]


# --------------------------------------------------------------------------------------
# generic/paperscope comparability + full leakage validation
# --------------------------------------------------------------------------------------


def _valid_pair(eval_ids, calibration_hash, model_inputs_hash):
    generic = _predictions_payload("generic", eval_ids, model_inputs_hash=model_inputs_hash, calibration_hash=NO_CALIBRATION)
    paperscope = _predictions_payload("paperscope", eval_ids, model_inputs_hash=model_inputs_hash, calibration_hash=calibration_hash)
    return generic, paperscope


def test_run_comparability_passes_for_matched_runs(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert errors == []


def test_run_comparability_rejects_model_mismatch(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["run"]["model"] = "a-different-model"
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert any("model mismatch" in e for e in errors)


def test_run_comparability_rejects_settings_mismatch(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["run"]["settings"] = {"temperature": 0.9}
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert any("settings mismatch" in e for e in errors)


def test_run_comparability_rejects_input_hash_mismatch(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["run"]["input_hash"] = "some-other-hash"
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert any("input_hash mismatch" in e for e in errors)


def test_run_comparability_rejects_generic_run_using_real_calibration_hash(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    generic["run"]["calibration_hash"] = manifest["calibration_hash"]  # generic must NOT claim calibration
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert any("calibration" in e for e in errors)


def test_run_comparability_rejects_paperscope_calibration_hash_mismatch(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["run"]["calibration_hash"] = "a-stale-or-tampered-hash"
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert any("frozen calibration_hash" in e for e in errors)


def test_run_comparability_rejects_different_forum_sets(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["predictions"] = paperscope["predictions"][:-1]
    errors = ev.validate_run_comparability(
        generic, paperscope, dataset_model_inputs_hash=manifest["model_inputs_hash"], dataset_calibration_hash=manifest["calibration_hash"]
    )
    assert any("different forum_id sets" in e for e in errors)


def test_full_leakage_validation_passes_for_a_clean_pair(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    gp, pp = tmp_path / "g.json", tmp_path / "p.json"
    gp.write_text(json.dumps(generic))
    pp.write_text(json.dumps(paperscope))

    report = ev.run_leakage_validation(out_dir, gp, pp)
    assert report.ok, report.violations


def test_full_leakage_validation_collects_multiple_violations_at_once(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["run"]["model"] = "different-model"
    paperscope["run"]["calibration_hash"] = "tampered"
    gp, pp = tmp_path / "g.json", tmp_path / "p.json"
    gp.write_text(json.dumps(generic))
    pp.write_text(json.dumps(paperscope))

    report = ev.run_leakage_validation(out_dir, gp, pp)
    assert not report.ok
    assert len(report.violations) >= 2


def test_dataset_consistency_detects_tampered_model_inputs(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, _manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    mi_path = out_dir / "model_inputs.jsonl"
    rows = [json.loads(line) for line in mi_path.read_text().splitlines()]
    rows[0]["title"] = "tampered title"
    mi_path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")

    errors = ev.validate_dataset_consistency(out_dir)
    assert any("model_inputs.jsonl content hash" in e for e in errors)


def test_dataset_consistency_detects_disallowed_field_injected_into_model_inputs(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    mi_path = out_dir / "model_inputs.jsonl"
    rows = [json.loads(line) for line in mi_path.read_text().splitlines()]
    rows[0]["decision"] = "accept"  # simulate a leaked field
    text = "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"
    mi_path.write_text(text)
    # Recompute the manifest hash so this test isolates the schema check, not the hash check.
    manifest_path = out_dir / "evaluation_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    from paperscope.models import content_hash

    manifest["model_inputs_hash"] = content_hash(text)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    errors = ev.validate_dataset_consistency(out_dir)
    assert any("disallowed fields" in e for e in errors)


# --------------------------------------------------------------------------------------
# metrics -- exact values
# --------------------------------------------------------------------------------------


def test_mean_absolute_error_exact():
    pairs = [(1.0, 2.0), (2.0, 2.0), (3.0, 6.0)]  # (actual, predicted)
    assert ev.mean_absolute_error(pairs) == pytest.approx((1 + 0 + 3) / 3, abs=1e-4)


def test_median_absolute_error_exact():
    pairs = [(1.0, 2.0), (2.0, 2.0), (3.0, 9.0)]  # errors: 1, 0, 6 -> median 1
    assert ev.median_absolute_error(pairs) == 1.0


def test_median_absolute_error_exact_even_count():
    pairs = [(0.0, 1.0), (0.0, 3.0), (0.0, 5.0), (0.0, 9.0)]  # errors 1,3,5,9 -> median (3+5)/2=4
    assert ev.median_absolute_error(pairs) == 4.0


def test_spearman_correlation_exact_known_case():
    # actual ranks [1,2,3], predicted ranks of [2,1,3] -> Pearson(ranks) = 0.5 (hand-derived)
    pairs = [(1.0, 2.0), (2.0, 1.0), (3.0, 3.0)]
    assert ev.spearman_correlation(pairs) == pytest.approx(0.5)


def test_spearman_correlation_perfect_monotonic():
    pairs = [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0), (4.0, 40.0)]
    assert ev.spearman_correlation(pairs) == pytest.approx(1.0)


def test_spearman_correlation_none_below_two_points():
    assert ev.spearman_correlation([(1.0, 1.0)]) is None
    assert ev.spearman_correlation([]) is None


def test_confusion_matrix_and_f1_exact():
    # actual, predicted
    pairs = [("accept", "accept"), ("accept", "accept"), ("accept", "reject"), ("reject", "accept"), ("reject", "reject")]
    cm = ev.confusion_matrix(pairs)
    assert cm == {"accept": {"accept": 2, "reject": 1}, "reject": {"accept": 1, "reject": 1}}
    metrics = ev.classification_metrics(cm)
    # tp=2, fn=1, fp=1, tn=1
    assert metrics["accuracy"] == pytest.approx(3 / 5, abs=1e-4)
    assert metrics["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert metrics["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert metrics["f1"] == pytest.approx(2 * (2 / 3) * (2 / 3) / ((2 / 3) + (2 / 3)), abs=1e-4)


def test_classification_metrics_handles_zero_denominators():
    cm = {"accept": {"accept": 0, "reject": 0}, "reject": {"accept": 0, "reject": 0}}
    metrics = ev.classification_metrics(cm)
    assert metrics == {"accuracy": None, "precision": None, "recall": None, "f1": None}


def test_brier_score_exact_with_probabilities():
    pairs = [(1, 0.8), (0, 0.3), (1, 0.4)]  # (actual, predicted_prob)
    expected = ((0.8 - 1) ** 2 + (0.3 - 0) ** 2 + (0.4 - 1) ** 2) / 3
    assert ev.brier_score(pairs) == pytest.approx(expected, abs=1e-4)


def test_ece_zero_for_perfectly_calibrated_bins():
    pairs = [(1, 1.0), (1, 1.0), (0, 0.0), (0, 0.0)]
    assert ev.expected_calibration_error(pairs) == pytest.approx(0.0)


# --------------------------------------------------------------------------------------
# probability metrics: skip conditions, no rating->probability approximation
# --------------------------------------------------------------------------------------


def _labels_all_resolved(n=25):
    return [
        {
            "forum_id": f"f{i}",
            "venue_family": "fam",
            "venue_year": 2025,
            "final_decision_eligible": True,
            "final_decision_target": "accept" if i % 2 == 0 else "reject",
        }
        for i in range(n)
    ]


def test_probability_metrics_computed_with_adequate_probabilities():
    labels = _labels_all_resolved(25)
    preds = {lbl["forum_id"]: {"accept_probability": 0.5} for lbl in labels}
    result = ev._probability_metrics(labels, preds)
    assert result["computed"] is True
    assert result["brier_score"] is not None


def test_probability_metrics_not_computed_when_no_probabilities_present():
    labels = _labels_all_resolved(25)
    preds = {lbl["forum_id"]: {"rating_prediction": 6.0, "decision_prediction": "accept", "accept_probability": None} for lbl in labels}
    result = ev._probability_metrics(labels, preds)
    assert result["computed"] is False
    assert result["reason"] == "no accept_probability values present"
    assert result["brier_score"] is None and result["ece"] is None


def test_probability_metrics_not_computed_below_min_sample_size():
    labels = _labels_all_resolved(5)
    preds = {lbl["forum_id"]: {"accept_probability": 0.6} for lbl in labels}
    result = ev._probability_metrics(labels, preds)
    assert result["computed"] is False
    assert "sample_size_below" in result["reason"]


def test_probability_never_approximated_from_rating_prediction():
    # A rating_prediction is present on every row but accept_probability is always None --
    # the probability metrics must treat this exactly like "no predictions" rather than
    # deriving a probability from the rating.
    labels = _labels_all_resolved(25)
    preds = {lbl["forum_id"]: {"rating_prediction": 9.9, "accept_probability": None} for lbl in labels}
    result = ev._probability_metrics(labels, preds)
    assert result["computed"] is False
    assert result["sample_size"] == 0


# --------------------------------------------------------------------------------------
# end-to-end evaluate(): stable output, offline-ness
# --------------------------------------------------------------------------------------


def test_evaluate_end_to_end_stable_json_and_markdown(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    gp, pp = tmp_path / "g.json", tmp_path / "p.json"
    gp.write_text(json.dumps(generic))
    pp.write_text(json.dumps(paperscope))

    results_dir_a = tmp_path / "results_a"
    results_dir_b = tmp_path / "results_b"
    ev.evaluate(
        dataset_dir=out_dir, generic_predictions_path=gp, paperscope_predictions_path=pp,
        output_dir=results_dir_a, generated_at="2026-01-01T00:00:00Z",
    )
    ev.evaluate(
        dataset_dir=out_dir, generic_predictions_path=gp, paperscope_predictions_path=pp,
        output_dir=results_dir_b, generated_at="2026-01-01T00:00:00Z",
    )
    assert (results_dir_a / "evaluation_results.json").read_text() == (results_dir_b / "evaluation_results.json").read_text()
    assert (results_dir_a / "evaluation_report.md").read_text() == (results_dir_b / "evaluation_report.md").read_text()

    results = json.loads((results_dir_a / "evaluation_results.json").read_text())
    assert results["leakage_checks"]["passed"] is True
    report_text = (results_dir_a / "evaluation_report.md").read_text()
    assert "PaperScope evaluation report" in report_text
    assert "Do not claim statistical significance" in report_text


def test_evaluate_raises_on_leakage_validation_failure(tmp_path, diverse_corpus_path, calibration_forums_path):
    out_dir, manifest = _prepared_dataset(tmp_path, diverse_corpus_path, calibration_forums_path)
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    paperscope["run"]["model"] = "wrong-model"
    gp, pp = tmp_path / "g.json", tmp_path / "p.json"
    gp.write_text(json.dumps(generic))
    pp.write_text(json.dumps(paperscope))

    with pytest.raises(ev.EvaluationValidationError):
        ev.evaluate(dataset_dir=out_dir, generic_predictions_path=gp, paperscope_predictions_path=pp, output_dir=tmp_path / "results")


def test_reviewer_aggregate_baseline_uses_only_calibration_aggregates(tmp_path, diverse_corpus_path, calibration_forums_path):
    records = _diverse_corpus()
    calibration_ids = set(json.loads(calibration_forums_path.read_text()))
    eval_ids = sorted(set(records) - calibration_ids)
    baseline = ev.compute_reviewer_aggregate_baseline(records, calibration_ids, eval_ids)
    assert baseline is not None
    # c01 rating=7.0, c02 rating=2.0 -> mean 4.5; both accept/reject once each -> majority is either (tie-break by max())
    assert baseline["run"]["settings"]["mean_initial_rating"] == pytest.approx(4.5)
    predicted_ids = {p["forum_id"] for p in baseline["predictions"]}
    assert predicted_ids == set(eval_ids)
    # Every eval forum gets the SAME constant prediction -- never its own true label.
    assert len({p["rating_prediction"] for p in baseline["predictions"]}) == 1


def test_reviewer_aggregate_baseline_none_when_calibration_forums_absent_from_corpus(tmp_path):
    records = _diverse_corpus()
    baseline = ev.compute_reviewer_aggregate_baseline(records, {"not-in-corpus"}, list(records))
    assert baseline is None


# --------------------------------------------------------------------------------------
# CLI wiring, offline guarantees
# --------------------------------------------------------------------------------------


def test_prepare_eval_cli_parses_args():
    from paperscope.cli import build_parser

    args = build_parser().parse_args(
        ["prepare-eval", "--corpus", "c.jsonl", "--calibration-forums", "cal.json", "--output", "out", "--seed", "7"]
    )
    assert args.corpus == "c.jsonl"
    assert args.seed == 7
    assert getattr(args, "needs_auth", False) is False


def test_evaluate_cli_parses_args():
    from paperscope.cli import build_parser

    args = build_parser().parse_args(
        ["evaluate", "--dataset", "d", "--generic-predictions", "g.json", "--paperscope-predictions", "p.json", "--output", "out"]
    )
    assert args.dataset == "d"
    assert getattr(args, "needs_auth", False) is False


def test_validate_eval_cli_parses_args():
    from paperscope.cli import build_parser

    args = build_parser().parse_args(
        ["validate-eval", "--dataset", "d", "--generic-predictions", "g.json", "--paperscope-predictions", "p.json"]
    )
    assert getattr(args, "needs_auth", False) is False


def _fail(*args, **kwargs):
    raise AssertionError("network/OpenReview client construction attempted by an offline command")


def test_evaluation_cli_workflow_never_constructs_openreview_client(tmp_path, diverse_corpus_path, calibration_forums_path, monkeypatch, capsys):
    from paperscope.cli import main

    monkeypatch.setattr(openreview, "Client", _fail)
    monkeypatch.setattr(openreview.api, "OpenReviewClient", _fail)

    out_dir = tmp_path / "dataset"
    main(["prepare-eval", "--corpus", str(diverse_corpus_path), "--calibration-forums", str(calibration_forums_path),
          "--output", str(out_dir), "--seed", "42"])

    manifest = json.loads((out_dir / "evaluation_manifest.json").read_text())
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    gp, pp = tmp_path / "g.json", tmp_path / "p.json"
    gp.write_text(json.dumps(generic))
    pp.write_text(json.dumps(paperscope))

    main(["validate-eval", "--dataset", str(out_dir), "--generic-predictions", str(gp), "--paperscope-predictions", str(pp)])
    main(["evaluate", "--dataset", str(out_dir), "--generic-predictions", str(gp), "--paperscope-predictions", str(pp),
          "--output", str(tmp_path / "results")])

    captured = capsys.readouterr()
    assert "auth mode" not in captured.out and "auth mode" not in captured.err


def test_evaluation_cli_workflow_makes_no_network_call(tmp_path, diverse_corpus_path, calibration_forums_path, monkeypatch):
    from paperscope.cli import main

    monkeypatch.setattr(socket, "socket", _fail)

    out_dir = tmp_path / "dataset"
    main(["prepare-eval", "--corpus", str(diverse_corpus_path), "--calibration-forums", str(calibration_forums_path),
          "--output", str(out_dir), "--seed", "42"])

    manifest = json.loads((out_dir / "evaluation_manifest.json").read_text())
    eval_ids = [json.loads(line)["forum_id"] for line in (out_dir / "model_inputs.jsonl").read_text().splitlines()]
    generic, paperscope = _valid_pair(eval_ids, manifest["calibration_hash"], manifest["model_inputs_hash"])
    gp, pp = tmp_path / "g.json", tmp_path / "p.json"
    gp.write_text(json.dumps(generic))
    pp.write_text(json.dumps(paperscope))

    main(["evaluate", "--dataset", str(out_dir), "--generic-predictions", str(gp), "--paperscope-predictions", str(pp),
          "--output", str(tmp_path / "results")])


def test_importing_evaluation_does_not_pull_in_anthropic():
    sys.modules.pop("anthropic", None)
    import paperscope.evaluation  # noqa: F401

    assert "anthropic" not in sys.modules


def test_evaluation_module_never_references_anthropic_or_openreview_client():
    import ast
    from pathlib import Path

    src = Path(__file__).parent.parent / "src" / "paperscope" / "evaluation.py"
    tree = ast.parse(src.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert "anthropic" not in names
    assert "openreview" not in names


def test_evaluation_operates_purely_from_explicit_paths_no_data_dir(tmp_path, monkeypatch):
    # Regression guard alongside test_no_data_directory_regression.py: nothing in this
    # module reads a relative "data/" path -- every function takes explicit Path args.
    monkeypatch.chdir(tmp_path)
    records = _diverse_corpus()
    corpus_path = tmp_path / "corpus.jsonl"
    storage.save_full_corpus(corpus_path, records)
    cal_path = tmp_path / "cal.json"
    cal_path.write_text(json.dumps(["c01", "c02"]))

    assert not (tmp_path / "data").exists()
    manifest = ev.prepare_eval(
        corpus_path=corpus_path, calibration_forums_path=cal_path, output_dir=tmp_path / "out", seed=42
    )
    assert manifest["eval_forum_count"] > 0
    assert not (tmp_path / "data").exists()
