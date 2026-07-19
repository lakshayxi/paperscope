# Evidence-grounded structured generation (Phase 3B)

The model's *only* output contract is structured JSON — a `{"claims": [...]}` object,
never free-text Markdown. Nothing reaches a reference file without first passing
structured validation against the statistics and evidence that grounded it. See
[`docs/statistics_and_evidence.md`](statistics_and_evidence.md) for `stats`/`evidence`,
which this phase builds directly on.

## The manual workflow

```
paperscope stats    --corpus data/full/iclr.jsonl --output artifacts/statistics
paperscope evidence  --corpus data/full/iclr.jsonl --output artifacts/evidence.json --seed 42
paperscope export-prompt --statistics artifacts/statistics/statistics.json \
                          --evidence artifacts/evidence.json \
                          --output artifacts/generation
# -> run through Claude Code by hand: read artifacts/generation/prompt.md, ground every
#    claim in artifacts/generation/{statistics,evidence}.json, and write the JSON
#    response (matching artifacts/generation/response_schema.json) to
#    artifacts/generation/claims.json
paperscope render --claims artifacts/generation/claims.json \
                   --statistics artifacts/generation/statistics.json \
                   --evidence artifacts/generation/evidence.json \
                   --output artifacts/reference.md
```

This is the **primary supported path** — no API key needed anywhere in it.
`export-prompt` and `render` never call an LLM; `render` re-validates its input before
rendering, so a hand-edited or hallucinated `claims.json` is rejected loudly rather than
silently rendered.

## `paperscope export-prompt`

```bash
paperscope export-prompt --statistics <statistics.json> --evidence <evidence.json> --output <dir>
```

Requires no API key. Errors immediately if the two inputs come from different corpora
(mismatched `corpus_hash`). Writes a self-contained bundle into `<dir>`:

| File | Contents |
|---|---|
| `prompt.md` | Versioned prompt: task, hard constraints, corpus scope summary, valid `section`/`claim_type`/`support_level` values — a pure function of the two inputs, so identical inputs produce byte-identical prompt text |
| `statistics.json` | Copy of the input statistics |
| `evidence.json` | Copy of the input evidence bundle |
| `response_schema.json` | JSON Schema for the expected `{"claims": [...]}` response, generated from the same constants `validate_claims` checks against |
| `manifest.json` | See Reproducibility below |

## The claim schema

```json
{
  "claim_id": "...",
  "section": "score_calibration | accept_signals | reject_signals | hidden_criteria | reviewer_language_patterns | year_over_year_drift | rebuttal_effectiveness",
  "claim_type": "deterministic_fact | evidence_excerpt | statistical_pattern | llm_interpretation | insufficient_evidence",
  "text": "...",
  "evidence_ids": ["ev_..."],
  "statistic_refs": ["iclr/2026/paper_mean_rating.mean"],
  "year_scope": [2026],
  "support_level": "strong | limited | single_instance | none",
  "limitations": ["..."]
}
```

`statistic_refs` use the format `"<venue_family>/<venue_year_or_all>/<metric>[.<dotted.path>]"`
— e.g. `"iclr/2026/paper_mean_rating.mean"` resolves the `mean` key inside that stat's
`value` dict; `"iclr/all/forum_count"` references the family-wide aggregate scope and is
treated as covering every year present for that family, not just one.

## Structured validation (`generation.validate_claims`)

Collects **every** violation before raising `GenerationValidationError` (never just the
first). Rejects:

- `evidence_id`s absent from the supplied bundle
- `statistic_ref`s that don't resolve to a real entry
- `deterministic_fact`/`statistical_pattern` claims whose `text` contains a digit but
  cite no `statistic_refs` — a number in `text` with no backing ref is treated as
  unsupported, never inferred by parsing the prose
- `evidence_excerpt` claims with no `evidence_ids`
- `evidence_excerpt` claims whose `text` isn't a verbatim substring of one of their
  cited excerpts (catches invented quotations)
- `year_scope` entries not present anywhere in the corpus ("unsupported venue/year
  scope")
- `year_scope` entries present in the corpus globally but not covered by *that claim's
  own* cited `evidence_ids`/`statistic_refs` ("exceeds its evidence scope" — a stricter,
  per-claim check distinct from the one above)
- duplicate `claim_id`s
- missing or invalid `support_level`
- empty `limitations`
- unrecognized `section` or `claim_type`

`paperscope render` always re-validates before rendering — there is no best-effort or
partial rendering path; an invalid claim blocks the whole render rather than being
silently dropped.

## `paperscope render`

```bash
paperscope render --claims <claims.json> --statistics <statistics.json> --evidence <evidence.json> --output <reference.md>
```

Pure Python, no LLM calls, deterministic (same validated claims always render to the
same Markdown regardless of input claim order). Groups claims by their `section` field
in a fixed order; within a section, sorts by `claim_id`. Every claim's block shows its
`claim_type` (labeled distinctly — "Deterministic fact" / "Evidence excerpt" / "Observed
statistical pattern" / "Model interpretation" / "Insufficient evidence"), support level,
year scope, cited statistics, cited evidence (as `forum <id>, note <id> — <source URL>`),
and limitations.

## Optional: `paperscope generate`

```bash
paperscope generate --provider anthropic --model <model> --prompt-dir artifacts/generation
```

Automates just the "ask the model" step of the manual workflow above, using a
previously-exported prompt bundle. Requires the `[llm]` extra
(`pip install -e ".[llm]"`) and an `ANTHROPIC_API_KEY`. `anthropic` is referenced in
exactly one file in this package, `src/paperscope/llm_provider.py`, and only inside a
function body — every other command, including `export-prompt` and `render`, has zero
dependency on it (enforced by `tests/test_optional_anthropic.py`, which scans every
file in `src/paperscope/`). The response is parsed (`generation.parse_provider_response`,
which tolerates a wrapping ` ```json ` fence but not actually-malformed JSON) and then
run through the same `validate_claims` as the manual path before `claims.json` is
written — a provider response gets no special trust.

## Reproducibility (`manifest.json`)

```json
{
  "content": {
    "corpus_hash": "9222deb94e5619fc",
    "evidence_bundle_hash": "...",
    "statistics_hash": "...",
    "prompt_version": "1.0",
    "schema_version": 1,
    "provider": null,
    "model": null,
    "generation_params": {}
  },
  "content_hash": "6c38926cb68664e4",
  "generated_at": "2026-07-19T00:15:23Z"
}
```

`content` is deterministic — two runs against identical statistics/evidence inputs (and,
for `generate`, identical provider/model/params) always produce an identical
`content_hash`, even though `generated_at` differs between runs. This is what makes
"did anything about the inputs actually change" a one-field comparison instead of a
manual diff.

## Limitations

- `statistic_refs` resolution only checks that the reference *resolves* — it does not
  parse or verify numbers appearing in a claim's free-text `text` beyond requiring that
  *some* `statistic_refs` entry is present when a digit appears. A claim could still cite
  a real, resolving `statistic_ref` while misstating the number in its own prose; nothing
  in this phase re-derives the claim's arithmetic from the cited value.
- The "exceeds evidence scope" check is purely about `year_scope` coverage — it doesn't
  check that a claim's *substance* is actually implied by its cited evidence/statistics,
  only that the years line up.
- `paperscope generate` has not been run against a live model in this repository yet —
  the manual `export-prompt` → Claude Code → `claims.json` → `render` path is the only
  one exercised end-to-end so far. See [`demo/sample_claims.json`](../demo/sample_claims.json)
  and [`demo/sample_reference.md`](../demo/sample_reference.md) for a worked (hand-authored,
  not model-generated) example against the real, small, single-year ICLR sample corpus.
