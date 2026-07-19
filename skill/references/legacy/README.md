# Legacy skill content (archival, unverified)

Everything in this directory predates the Phase 4A skill redesign (see
[`docs/skill_building.md`](../../../docs/skill_building.md)). It is **hand-written prose**,
never passed through the structured claim schema (`generation.validate_claims`) that
every file under `skill/references/<family>.md` (one level up) is now required to pass.

| File | What it was |
|---|---|
| `SKILL.md.legacy` | The original skill definition -- included "senior ML researcher with area-chair-level experience" and "matches the actual distribution of accepted/rejected papers" framing, and fell back to ICLR conventions for any unrecognized venue. Both are things the redesigned skill explicitly no longer does. |
| `iclr.md`, `neurips.md`, `icml.md`, `cvpr.md` | Hand-accumulated calibration notes, tagged `*(real ICLR 2024)*` etc. where a pattern came from a real fetched batch, but never independently re-verified against a stored evidence bundle or hash-checked provenance. |

## Why this exists

The project's [`CLAUDE.md`](../../../CLAUDE.md) skill-update rule is "never delete
existing patterns" -- this directory is that rule applied to the redesign itself, not
just to future additions. The notes here reflect real work and, in several cases, real
excerpted OpenReview data; they're preserved for continuity and as a source to
eventually re-derive validated claims from, not discarded.

## What "archival" means here, concretely

- **Never loaded automatically.** `skill/SKILL.md`'s venue-resolution instructions
  (Step 0) only ever load `references/<family>.md` paths listed in `manifest.json`'s
  `content.venues` map -- that map is built exclusively from validated claims and never
  contains a path under `references/legacy/`. `paperscope validate-skill` fails the
  build if it ever does (see `skill_builder.validate_skill`).
- **Not validated.** No claim here carries a `support_level`, `claim_type`, or
  evidence/statistic provenance link. Treat every specific number or quote as
  unverified until it's re-derived through `paperscope stats` / `paperscope evidence` /
  `paperscope export-prompt` / `paperscope build-skill` and lands in a real
  `references/<family>.md` file.
- **Preserved verbatim.** `paperscope build-skill` copies this directory forward,
  byte-for-byte, on every rebuild of `skill/` -- it is never regenerated, edited, or
  pruned by the builder.
