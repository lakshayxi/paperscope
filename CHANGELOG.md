# Changelog

## Unreleased

### Added
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

### Fixed
- `anthropic` was imported unconditionally at module load, breaking fetch-only usage
  without it installed — it's now an optional import scoped to LLM generation only.
- Author/keyword list fields from the OpenReview API were being stringified as Python
  repr text instead of joined, due to `get_field` eagerly converting non-dict values.
- The v2 bulk-fetch path re-fetched the same first *n* notes on every run instead of
  advancing past previously-seen notes (no cursor was used) — fixed with `after`-based
  pagination and a persisted per-venue cursor.
