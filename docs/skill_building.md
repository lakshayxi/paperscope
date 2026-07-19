# Building and validating the skill (Phase 4A)

`paperscope build-skill` turns Phase 3's validated structured claims into an installable
Claude Code skill. It never generates content from unvalidated Markdown, makes no LLM or
network calls, and is deterministic: the same claims/statistics/evidence inputs always
produce a byte-identical skill (aside from the recorded `generated_at` timestamp). See
`src/paperscope/skill_builder.py` for the implementation and its module docstring for the
full fail-closed contract.

## The workflow

```bash
paperscope stats    --corpus data/full/iclr.jsonl --output artifacts/statistics
paperscope evidence  --corpus data/full/iclr.jsonl --output artifacts/evidence_bundle.json --seed 42
# -> hand-author (or export-prompt/render through Claude Code, see docs/generation.md)
#    artifacts/claims.json, grounded against the two files above and passing
#    generation.validate_claims
paperscope build-skill --claims artifacts/claims.json \
                        --statistics artifacts/statistics/statistics.json \
                        --evidence artifacts/evidence_bundle.json \
                        --output skill
paperscope validate-skill --path skill
```

`build-skill` re-validates `claims.json` itself before writing anything -- it does not
trust that a caller already validated it. A build that fails at any point (schema
mismatch, corpus hash mismatch, invalid claims, ambiguous claim attribution, or its own
post-build self-validation) leaves `--output` exactly as it was before the call; see
Atomicity below.

## What gets built

```
skill/
├── SKILL.md                    # generated -- venue resolution, review modes, rules
├── manifest.json                 # generated -- machine-readable reference manifest
├── references/
│   ├── <family>.md               # generated -- one per venue family in scope
│   └── legacy/                   # untouched -- carried forward byte-for-byte, never
│                                  # generated, edited, or referenced by the manifest
```

### `manifest.json`

```json
{
  "content": {
    "skill_schema_version": 1,
    "paperscope_version": "0.1.0",
    "supported_venue_families": ["iclr"],
    "venues": {
      "iclr": {
        "reference": "references/iclr.md",
        "reference_hash": "...",
        "aliases": ["International Conference on Learning Representations"],
        "years_covered": [2026],
        "forum_count": 10,
        "review_count": 37,
        "evidence_count": 27,
        "decisions_resolved": 0,
        "claim_count": 10,
        "preliminary": true
      }
    },
    "unsupported_mode": "generic_uncalibrated",
    "corpus_hash": "...",
    "statistics_hash": "...",
    "evidence_bundle_hash": "...",
    "claims_hash": "...",
    "source_schema_versions": {"stats": 1, "evidence": 1, "generation": 1}
  },
  "content_hash": "...",
  "generated_at": "2026-07-19T18:34:27Z"
}
```

`content` is deterministic and hashed separately from `generated_at`, same pattern as
`generation.build_manifest` (Phase 3B) -- two builds from identical inputs produce an
identical `content_hash` regardless of when they ran. `venues` is the **only** source of
truth `references/legacy/` is exempt from: `paperscope validate-skill` fails if any
`reference` path resolves into `references/legacy/`.

### Venue attribution

A build can cover more than one venue family if its input statistics/evidence do. Each
claim is attributed to a family by the `venue_family` its `statistic_refs`/`evidence_ids`
resolve to. A claim with no refs at all (a bare `insufficient_evidence` statement) is
attached to the sole family present when the build is single-family; in a multi-family
build such a claim is rejected outright (`SkillBuildError`, "ambiguous attribution") --
there's no way to guess which venue it belongs to, so the build fails closed rather than
silently misattributing it or dropping it.

### Venue resolution (runtime)

`src/paperscope/venue_resolution.py` implements the lookup `SKILL.md` describes in
prose: exact, case/whitespace-insensitive match against a family's key or a manifest-
declared alias, nothing fuzzier. No match -> `generic_uncalibrated`. More than one match
(an invalid manifest) -> `ambiguous`, never a silent guess. There is no fallback to any
specific family (including ICLR) for an unrecognized venue. Kept in Python specifically
so this logic is unit-testable rather than only described in Markdown -- see
`tests/test_venue_resolution.py`.

### Atomicity

`build_skill` writes everything to a private `<output>.tmp<pid>` directory, runs
`validate_skill` against it, and only then swaps it into place (`os.rename`, with the
previous directory kept as `<output>.prev<pid>` until the swap succeeds). Anything that
raises before the swap -- an invalid input, a self-validation failure -- never touches
`--output`; the temp directory is removed and the previous build (if any) is left intact.
See `tests/test_skill_builder.py::test_atomic_build_failure_does_not_corrupt_existing_valid_skill`.

## `paperscope validate-skill`

Collects **every** violation before reporting (never stops at the first). Checks:

- `SKILL.md` and `manifest.json` exist and `SKILL.md`'s frontmatter has a valid
  `name`/`description`
- `manifest.json`'s schema (required keys, `content_hash` matches its own `content`,
  `skill_schema_version` matches)
- every `venues[family].reference` file exists and its hash matches
  `reference_hash` (catches a tampered or stale reference)
- every reference embeds the manifest's `corpus_hash` (internal consistency between the
  manifest and the file it describes)
- no `venues[family].reference` resolves into `references/legacy/`
- no alias collides across families (`venue_resolution.find_alias_collisions`)
- `SKILL.md` defines `generic_uncalibrated` mode and mentions all three review modes
  (`quick`/`full`/`rebuttal`)
- none of `FORBIDDEN_PHRASES` (lifted from the pre-redesign skill -- "area-chair-level
  experience", "actual distribution of accepted", "apply ICLR conventions as a neutral
  default") appear anywhere in `SKILL.md` or a non-legacy `references/*.md` file.
  `references/legacy/*` is explicitly exempt from this scan -- it's archival by design,
  see `skill/references/legacy/README.md`.

## Review modes and input tiers

Both are defined as Python constants in `skill_builder.py` (`REVIEW_MODES`,
`INPUT_TIERS`) and rendered into `SKILL.md` deterministically, rather than hand-written
prose that could drift from what the builder actually encodes:

| Mode | Required input | Unsupported venue |
|---|---|---|
| `quick` | Title + abstract | `generic_uncalibrated`, stated explicitly |
| `full` | Full paper text | `generic_uncalibrated`, stated explicitly |
| `rebuttal` | Full paper text + author rebuttal | `generic_uncalibrated`, stated explicitly |

Input tiers are ordered (title+abstract < paper text < paper+supplementary <
paper+rebuttal) and `SKILL.md` states explicitly that a lower tier is never treated as
equivalent to a higher one -- an abstract-only "quick" review is never presented as a
full-paper review.

## Legacy isolation

`skill/references/legacy/` holds the pre-redesign, hand-written `SKILL.md` and per-venue
reference files (see `skill/references/legacy/README.md`). `build_skill` copies this
directory forward unchanged on every rebuild -- it never generates, edits, or references
anything inside it. `paperscope validate-skill` actively checks that no manifest entry
points there, and `tests/test_skill_builder.py` has dedicated coverage
(`test_legacy_references_carried_forward_and_unreachable`,
`test_skill_md_instructs_never_to_load_legacy`) proving it stays unreachable through
normal venue selection.

## Redistribution note

A venue reference's `evidence_excerpt` claims quote real review text. Keep any such
quote within the project's public-excerpt norm (`PUBLIC_EXCERPT_MAX_CHARS`, currently
280 chars -- see `docs/redistribution.md`) when hand-authoring `claims.json`, even though
`paperscope evidence`'s own excerpt bound (`EVIDENCE_EXCERPT_MAX_CHARS`, 600 chars) is
longer -- the evidence bundle itself is local-only and gitignored (`artifacts/`), but a
built `skill/references/<family>.md` is committed, so a claim's quoted `text` is what
actually gets redistributed, not the full excerpt behind it.

## Known limitations (Phase 4A)

- Single-corpus builds only: `build-skill` takes one statistics/evidence pair per
  invocation. Multi-venue skills are supported (a build can cover every family present
  in the input), but there's no merge command yet for combining two separately-built
  skills -- rebuild from a corpus covering everything you want included.
- `claims.json` is still hand-authored or produced via the Phase 3B manual
  `export-prompt` -> Claude Code -> `render`-equivalent workflow; nothing in Phase 4A
  automates writing claims from a corpus.
- The real `skill/references/iclr.md` shipped in this repo is preliminary by its own
  `manifest.json` (`preliminary: true`, `decisions_resolved: 0`, one venue-year) -- see
  the checkpoint report for exact numbers. It will improve automatically as the
  scheduled fetch automation accumulates more data and review cycles resolve.
