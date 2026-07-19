#!/usr/bin/env python3
"""Deterministic external runner for Phase 4B evaluation predictions.

NOT part of the `paperscope` package and not invoked by its test suite or CI -- this is
the manual, external step `docs/evaluation.md` describes between `prepare-eval` and
`validate-eval`/`evaluate`. Deliberately kept standalone rather than a new `paperscope`
subcommand so `anthropic` (required here) never enters the core CLI's import graph --
see `tests/test_optional_anthropic.py`, which scans every file *inside* `src/paperscope/`
for an `anthropic` reference; this script lives outside that tree on purpose.

Requires `ANTHROPIC_API_KEY` and the `anthropic` package (`pip install paperscope[llm]`).

Leakage discipline: reads ONLY `<dataset>/model_inputs.jsonl` and
`<dataset>/evaluation_manifest.json` (for hashes). Never opens `private_labels.jsonl`,
the source corpus, or any file that could contain a review, rebuttal, rating, or
decision -- the model sees exactly what `model_inputs.jsonl` already restricts it to
(forum_id, venue_family, venue_year, title, abstract), the same guarantee `prepare-eval`
enforces on the dataset side.

Usage (see docs/evaluation.md for the full pilot workflow -- and note that a
`--system paperscope` run additionally requires a venue reference that was itself built
from *this* dataset's frozen calibration subset; this script does not build one, only
records the dataset's calibration_hash as a schema field. Building that reference is a
separate, prerequisite step -- see the checkpoint report for exact commands):

    python scripts/generate_predictions.py --dataset artifacts/eval_pilot/dataset \\
        --system generic --model claude-sonnet-5 --temperature 0.0 --max-tokens 1024 \\
        --output artifacts/eval_pilot/generic_predictions.json

    python scripts/generate_predictions.py --dataset artifacts/eval_pilot/dataset \\
        --system paperscope --model claude-sonnet-5 --temperature 0.0 --max-tokens 1024 \\
        --reference skill/references/iclr.md \\
        --output artifacts/eval_pilot/paperscope_predictions.json

Both invocations MUST share --dataset/--model/--temperature/--max-tokens -- the only
allowed difference is whether --reference is supplied (see `_build_prompt`: the shared
prompt template is identical either way, just missing the reference block when absent).
Re-running with the same --output resumes: forum_ids that already have a schema-valid
prediction are not re-sent to the model, so a run interrupted partway (or one that hit a
malformed response on some forums) can be repeated to fill in only what's missing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

PAPERSCOPE_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(PAPERSCOPE_SRC))

from paperscope.evaluation import NO_CALIBRATION, validate_prediction_schema  # noqa: E402
from paperscope.models import content_hash  # noqa: E402

VALID_SYSTEMS = ("generic", "paperscope")
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# The one prompt skeleton both systems use, verbatim -- {reference_block} is the ONLY
# thing that differs between a generic and a paperscope run, per the module docstring.
# Hashed (unfilled) as `prompt_hash` so both runs -- and any later rerun -- can prove
# they used byte-identical instructions.
PROMPT_TEMPLATE = """You are reviewing a paper submitted to {venue_family_upper} {venue_year}, \
using ONLY the title and abstract below -- no other information about this paper is \
available to you, and none should be assumed.
{reference_block}
Title: {title}

Abstract: {abstract}

Respond with ONLY a single JSON object, no Markdown code fence, no commentary before or \
after it, matching exactly this shape:

{{"rating_prediction": <a number from 1 to 10, your predicted average reviewer rating>, \
"decision_prediction": "accept" or "reject", \
"accept_probability": <a number from 0 to 1, your estimated probability of acceptance>, \
"reasoning_summary": "<one or two sentences on why>"}}

Do not invent facts about the paper beyond what the title and abstract state. Do not \
mention that you are missing the full text, reviews, or any other material -- just give \
your best calibrated judgment from the title and abstract alone.
"""

REFERENCE_BLOCK_TEMPLATE = """
You have access to the following venue-calibration reference, built from real past \
{venue_family_upper} peer reviews. Use it to calibrate your rating/decision -- it \
reflects patterns observed in actual accepted/rejected papers at this venue, not \
generic reviewing heuristics.

--- BEGIN VENUE REFERENCE ---
{reference_text}
--- END VENUE REFERENCE ---
"""


def _load_model_inputs(dataset_dir: Path) -> list[dict]:
    path = dataset_dir / "model_inputs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_dataset_manifest(dataset_dir: Path) -> dict:
    return json.loads((dataset_dir / "evaluation_manifest.json").read_text())


def _build_prompt(model_input: dict, reference_text: str | None) -> str:
    reference_block = (
        REFERENCE_BLOCK_TEMPLATE.format(
            venue_family_upper=model_input["venue_family"].upper(), reference_text=reference_text
        )
        if reference_text
        else ""
    )
    return PROMPT_TEMPLATE.format(
        venue_family_upper=model_input["venue_family"].upper(),
        venue_year=model_input["venue_year"],
        reference_block=reference_block,
        title=model_input["title"],
        abstract=model_input["abstract"],
    )


def _validate_model_output(obj: object) -> list[str]:
    """Fail-closed structural check on one raw model response, before it's ever written
    to the output file. Mirrors (a strict subset of) `validate_prediction_schema`'s
    per-record rules, applied to the model's raw JSON before `forum_id` is even attached.
    """
    if not isinstance(obj, dict):
        return ["response is not a JSON object"]
    errors = []
    rating = obj.get("rating_prediction")
    if rating is not None and not isinstance(rating, (int, float)):
        errors.append("rating_prediction must be numeric or null")
    decision = obj.get("decision_prediction")
    if decision is not None and decision not in ("accept", "reject"):
        errors.append("decision_prediction must be 'accept', 'reject', or null")
    prob = obj.get("accept_probability")
    if prob is not None and (not isinstance(prob, (int, float)) or isinstance(prob, bool) or not (0.0 <= prob <= 1.0)):
        errors.append("accept_probability must be a number in [0, 1] or null")
    if "reasoning_summary" in obj and obj["reasoning_summary"] is not None and not isinstance(obj["reasoning_summary"], str):
        errors.append("reasoning_summary must be a string")
    return errors


def _parse_response(raw_text: str) -> dict:
    text = _CODE_FENCE_RE.sub("", raw_text.strip()).strip()
    return json.loads(text)  # raises json.JSONDecodeError on malformed output -- caller catches it


def _call_model(client, *, model: str, temperature: float, max_tokens: int, prompt: str) -> str:
    message = client.messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if getattr(block, "type", None) == "text")


def _load_existing_output(path: Path, *, expected_run: dict) -> dict:
    """Resume support: an existing output file is only reused if its `run` metadata
    matches this invocation's exactly (model/settings/input_hash/calibration_hash/system)
    -- fails closed rather than silently merging predictions generated under different
    settings into one file.
    """
    if not path.exists():
        return {"run": expected_run, "predictions": []}
    existing = json.loads(path.read_text())
    existing_run = {k: v for k, v in existing.get("run", {}).items() if k != "created_at"}
    compare_expected = {k: v for k, v in expected_run.items() if k != "created_at"}
    if existing_run != compare_expected:
        sys.exit(
            f"{path} already exists with different run settings than this invocation -- "
            f"refusing to resume into it (existing={existing_run}, requested={compare_expected}). "
            f"Use a different --output or move the old file aside."
        )
    return existing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="Directory written by `paperscope prepare-eval`")
    parser.add_argument("--system", required=True, choices=VALID_SYSTEMS)
    parser.add_argument("--model", required=True, help="Model id, e.g. claude-sonnet-5 -- must match exactly across the generic/paperscope pair")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--reference", default=None,
                         help="Path to a validated venue reference (e.g. skill/references/iclr.md). "
                              "Required for --system paperscope, forbidden for --system generic.")
    parser.add_argument("--output", required=True, help="Output predictions JSON path (resumable)")
    parser.add_argument("--run-id", default=None, help="Defaults to '<system>_<model>_<unix-time>'")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N forums (for smoke-testing)")
    args = parser.parse_args()

    if args.system == "paperscope" and not args.reference:
        parser.error("--system paperscope requires --reference <path to a venue reference>")
    if args.system == "generic" and args.reference:
        parser.error("--system generic must not be given --reference -- the whole point of the generic run is no calibration")

    import anthropic  # local import, mirrors llm_provider.py -- only this script needs it

    dataset_dir = Path(args.dataset)
    manifest = _load_dataset_manifest(dataset_dir)
    model_inputs = _load_model_inputs(dataset_dir)
    if args.limit:
        model_inputs = model_inputs[: args.limit]

    reference_text = Path(args.reference).read_text() if args.reference else None
    calibration_hash = manifest["calibration_hash"] if args.system == "paperscope" else NO_CALIBRATION
    prompt_hash = content_hash(PROMPT_TEMPLATE, REFERENCE_BLOCK_TEMPLATE)

    run_meta = {
        "run_id": args.run_id or f"{args.system}_{args.model}_{int(time.time())}",
        "system": args.system,
        "model": args.model,
        "settings": {"temperature": args.temperature, "max_tokens": args.max_tokens, "prompt_hash": prompt_hash},
        "input_hash": manifest["model_inputs_hash"],
        "calibration_hash": calibration_hash,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    output_path = Path(args.output)
    existing = _load_existing_output(output_path, expected_run=run_meta)
    predictions_by_forum = {p["forum_id"]: p for p in existing["predictions"]}
    already_done = set(predictions_by_forum)

    client = anthropic.Anthropic()
    failures: list[tuple[str, str]] = []
    todo = [mi for mi in model_inputs if mi["forum_id"] not in already_done]
    print(f"{len(already_done)} already done, {len(todo)} to generate ({args.system}, {args.model})")

    for i, mi in enumerate(todo, 1):
        prompt = _build_prompt(mi, reference_text)
        try:
            raw_text = _call_model(client, model=args.model, temperature=args.temperature, max_tokens=args.max_tokens, prompt=prompt)
            parsed = _parse_response(raw_text)
        except (json.JSONDecodeError, anthropic.APIError) as e:
            failures.append((mi["forum_id"], str(e)))
            print(f"  [{i}/{len(todo)}] {mi['forum_id']}: FAILED ({e}) -- leaving unpredicted, safe to retry", file=sys.stderr)
            continue

        errors = _validate_model_output(parsed)
        if errors:
            failures.append((mi["forum_id"], "; ".join(errors)))
            print(f"  [{i}/{len(todo)}] {mi['forum_id']}: FAILED schema check ({errors}) -- leaving unpredicted", file=sys.stderr)
            continue

        predictions_by_forum[mi["forum_id"]] = {
            "forum_id": mi["forum_id"],
            "rating_prediction": parsed.get("rating_prediction"),
            "decision_prediction": parsed.get("decision_prediction"),
            "accept_probability": parsed.get("accept_probability"),
            "reasoning_summary": parsed.get("reasoning_summary", ""),
        }
        print(f"  [{i}/{len(todo)}] {mi['forum_id']}: ok")

        # Write incrementally -- a crash/interrupt partway through never loses completed
        # work, and the file is always resumable from exactly where it left off.
        payload = {"run": run_meta, "predictions": [predictions_by_forum[fid] for fid in sorted(predictions_by_forum)]}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    final_payload = {"run": run_meta, "predictions": [predictions_by_forum[fid] for fid in sorted(predictions_by_forum)]}
    schema_errors = validate_prediction_schema(final_payload)
    if schema_errors:
        sys.exit(f"final output failed its own prediction schema validation (should be impossible): {schema_errors}")

    print(f"wrote {len(predictions_by_forum)}/{len(model_inputs)} predictions to {output_path}")
    if failures:
        print(f"{len(failures)} forum(s) failed and were left unpredicted -- rerun this same command to retry them:", file=sys.stderr)
        for fid, reason in failures:
            print(f"  - {fid}: {reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
