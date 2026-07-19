# Changelog

## Unreleased

### Added
- `paperscope prepare-eval` / `paperscope validate-eval` / `paperscope evaluate`
  (`src/paperscope/evaluation.py`, Phase 4B): a leakage-safe, fully offline evaluation
  harness for saved prediction files -- no LLM/API calls anywhere in this module.
  `prepare-eval` freezes and hashes a calibration forum-ID set *before* selecting
  evaluation forums (`corpus forums - calibration forums`, further excluding forums with
  no usable initial-rating/decision label or no title/abstract), and writes a
  model-visible `model_inputs.jsonl` (a closed schema: forum_id/venue/title/abstract/
  input_tier only -- no review, rebuttal, decision, or rating field can ever appear on
  it) plus a separate `private_labels.jsonl` never intended for model context.
  Initial-rating and final-decision are two independent tasks with their own
  eligibility/target fields per forum -- final-decision is read directly from
  `Decision.normalized`, never derived from a rating threshold, and withdrawn/desk-
  rejected/unresolved forums are excluded from that task's eligible pool (counts still
  reported). `validate-eval`/`evaluate` collect every leakage/comparability violation
  (dataset hash consistency, calibration/evaluation disjointness, prediction schema,
  dataset membership, and generic-vs-PaperScope run comparability -- identical model/
  settings/input hashes and forum sets, calibration reference the only allowed
  difference) before failing, and `evaluate` re-runs every check itself rather than
  trusting a prior `validate-eval` pass. Metrics: MAE/median absolute error/Spearman
  (pure Python, no numpy/scipy) for initial-rating; accuracy/precision/recall/F1/
  confusion matrix for final-decision; Brier score/ECE only when `accept_probability` is
  present for an adequate sample -- never approximated from `rating_prediction`. An
  optional reviewer-aggregate baseline predicts a constant rating/decision derived only
  from calibration-set aggregates, never an eval forum's own label. See
  `docs/evaluation.md` and the synthetic fixtures under `demo/eval/`.
- `paperscope build-skill` / `paperscope validate-skill`
  (`src/paperscope/skill_builder.py`, Phase 4A): builds an installable
  `paperscope-reviewer` Claude Code skill from validated Phase 3 claims/statistics/
  evidence, and validates one. Re-validates `claims.json` itself before writing
  anything, never generates content from unvalidated Markdown, makes no LLM or network
  calls, is deterministic (identical inputs -> identical `manifest.json` `content_hash`,
  independent of the recorded `generated_at`), and writes atomically -- a build to
  temp + self-validate + swap, so a failed build never leaves `--output` partially
  updated. `validate-skill` collects every violation (missing/tampered reference files,
  a manifest pointing into `references/legacy/`, alias collisions, missing
  `generic_uncalibrated` mode, forbidden overclaim phrases) rather than stopping at the
  first. See `docs/skill_building.md`.
- `src/paperscope/venue_resolution.py`: deterministic venue-reference resolution --
  exact, case/whitespace-insensitive match against a family key or a manifest-declared
  alias only, never fuzzy/heuristic matching and never a fallback to a specific family
  (e.g. ICLR) for an unrecognized venue. Kept as plain, unit-testable Python rather than
  prose-only logic.
- The generated skill defines three explicit review modes (`quick`/`full`/`rebuttal`)
  and four input tiers (title+abstract / paper text / paper+supplementary /
  paper+rebuttal), each with required/optional input, output depth, and limitations
  spelled out -- an abstract-only review is never presented as equivalent to a
  full-paper review.
- `skill/references/legacy/`: the pre-redesign, hand-written `SKILL.md` and per-venue
  reference files, preserved verbatim with an archival banner. `build-skill` copies this
  directory forward unchanged on every rebuild; it is never generated, edited, or
  referenced by `manifest.json`, and `validate-skill` fails closed if it ever is.
- `skill/references/iclr.md` + `skill/manifest.json`: a real, generated, preliminary
  ICLR reference built from the actual fetched corpus (10 forums, ICLR 2026, an active
  review cycle -- `decisions_resolved: 0`). Year-over-year drift and rebuttal
  effectiveness are both explicit `insufficient_evidence` claims, not smoothed over.
- `paperscope export-prompt` / `paperscope render` (`src/paperscope/generation.py`):
  evidence-grounded structured generation. The model's only output contract is
  structured JSON (`{"claims": [...]}`, never free-text Markdown); `validate_claims`
  rejects unresolvable evidence/statistic references, invented quotations, numeric
  claims with no statistic backing, duplicate claim IDs, unsupported or over-reaching
  venue/year scope, and missing limitations/support levels, collecting every violation
  before raising. `render` always re-validates before rendering, so nothing reaches
  Markdown without passing structured validation first. `export-prompt` needs no API key
  and writes a self-contained bundle (prompt, statistics, evidence, response schema,
  reproducibility manifest) for the primary supported manual workflow (Claude Code by
  hand). See `docs/generation.md`.
- `paperscope generate` (optional, `src/paperscope/llm_provider.py`): automates the
  "ask the model" step behind the `[llm]` extra. `anthropic` is referenced in exactly
  this one file in the package, and only inside a function body — every other command
  has zero dependency on it, enforced by `tests/test_optional_anthropic.py`.
- `paperscope stats` (`src/paperscope/statistics.py`): deterministic, venue/year-scoped
  corpus statistics (counts, missing-data rates, rating/confidence distributions,
  decision distribution, paper-level mean/variance, reviewer disagreement, initial-to-
  final rating changes, and an explicitly observational rebuttal-present vs. absent
  comparison), written as machine-readable `statistics.json` plus a deterministic
  Markdown summary.
- `paperscope evidence` (`src/paperscope/evidence.py`): bounded, seeded evidence-bundle
  generation stratified across decision/rating/year/disagreement/rebuttal axes, with full
  per-excerpt provenance and validation that rejects unknown IDs, duplicate evidence IDs,
  hash/excerpt mismatches, held-out overlap, and unsupported venue/year claims. See
  `docs/statistics_and_evidence.md`.
- `src/paperscope/` package: paper-centric corpus schema (`ForumRecord`), OpenReview
  client with token/guest-mode support, cursor-based pagination, seeded deterministic
  acquisition sampling, a refresh policy for scheduled re-fetching, two-tier storage
  (full local corpus + redistribution-conscious public index), and a `paperscope` CLI.
- `pyproject.toml` packaging, `LICENSE` (MIT), test suite, CI workflow.
- Scheduled GitHub Actions fetch automation persisting state to a dedicated `data` branch.

### Changed
- `expl.py` is now a compatibility shim that explicitly translates legacy `bulk`/`forum`
  commands into the new `paperscope` CLI. `analyze`/`skill`/`all` are not yet available
  under the new CLI (planned for a later phase) and print a clear message instead of
  silently behaving differently.
- The installable skill (`skill/`) is now generated by `paperscope build-skill`, not
  hand-edited. The redesign removes "area-chair-level experience" and "actual
  distribution of accepted/rejected papers" framing, no longer silently applies ICLR
  conventions to an unrecognized venue (unsupported venues now get explicit
  `generic_uncalibrated` mode), and only advertises venue families with an actual
  validated reference -- today that's ICLR only, down from the four families
  (ICLR/NeurIPS/ICML/CVPR) the old hand-written `skill/references/` claimed.

### Fixed
- `anthropic` was imported unconditionally at module load, breaking fetch-only usage
  without it installed — it's now an optional import scoped to LLM generation only.
- Author/keyword list fields from the OpenReview API were being stringified as Python
  repr text instead of joined, due to `get_field` eagerly converting non-dict values.
- The v2 bulk-fetch path re-fetched the same first *n* notes on every run instead of
  advancing past previously-seen notes (no cursor was used) — fixed with `after`-based
  pagination and a persisted per-venue cursor.
