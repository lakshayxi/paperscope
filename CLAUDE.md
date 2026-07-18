# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PaperScope is a tool for building venue-calibrated ML paper reviewer skills from real OpenReview data. It fetches peer reviews, and Claude manually reads them to update skill reference files — no Claude API required for the learning loop.

## Setup

```bash
pip install openreview-py anthropic
export OPENREVIEW_USERNAME='your@email.com'
export OPENREVIEW_PASSWORD='yourpassword'
```

The `anthropic` package and `ANTHROPIC_API_KEY` are only needed if using the `analyze` or `all` subcommands (Claude API pipeline). The primary workflow — fetch + manual learning — does not require them.

## Primary Workflow (Manual Learning Loop)

```bash
# Fetch a batch into corpus + inbox
python expl.py bulk --venues iclr --years 2026 --per-venue 20

# Claude reads corpus_iclr_inbox.json, updates skill/references/iclr.md, then:
rm corpus_iclr_inbox.json
git add skill/references/iclr.md && git commit -m "added patterns from batch N"
```

Each run appends new reviews to `corpus_iclr.json` and writes only the **new** reviews to `corpus_iclr_inbox.json`. Seen forum IDs are tracked in `.seen_<venue_id>.json` so reviews never repeat across runs.

## CLI Subcommands

```bash
python expl.py bulk --venues iclr neurips --years 2024 2025 --per-venue 20
python expl.py forum --url "https://openreview.net/forum?id=XXX"
python expl.py analyze --corpus corpus_iclr.json   # uses Claude API
python expl.py skill                                # writes skill/ from analysis
python expl.py all                                  # full Claude API pipeline
```

`--venues` accepts family names: `iclr neurips icml acl cvpr aaai kdd`

## File Layout

- `corpus_<family>.json` — accumulated reviews per venue family (gitignored)
- `corpus_<family>_inbox.json` — new reviews from the last run only (gitignored, delete after reading)
- `.seen_<venue_id>.json` — tracks seen forum IDs to prevent repeats (gitignored)
- `skill/SKILL.md` — the skill definition and review template
- `skill/references/{venue}.md` — one calibration file per venue group, updated manually

## Architecture of expl.py

Everything lives in `expl.py`. Key internals:

**`_fetch_notes(client, venue_id, inv, version, n)`** — the core fetcher. For v2 API (ICLR, NeurIPS etc.), the global invitation stream is often empty; it falls back to sampling submissions then fetching child notes per forum. For v1, uses `get_notes` with random offset.

**`discover_review_invitation()`** — probes multiple invitation ID patterns; treats HTTP 403 as "invitation exists but metadata restricted" (still usable).

**`build_corpus()`** — iterates `VENUES`, deduplicates against `.seen_*.json`, writes corpus incrementally after each venue (crash-safe), writes inbox with only new reviews.

**`VENUES`** — list of `(display_name, venue_id, api_version, suffix)` tuples at the top of the file.

**`VENUE_GROUPS`** — maps family name → list of display names to merge (e.g., `"iclr"` → `["ICLR 2023", "ICLR 2024", "ICLR 2025", "ICLR 2026"]`).

## Adding a New Venue

1. Add to `VENUES`: `("CONF YEAR", "venue.org/CONF/YEAR/Conference", "v2", "Official_Review")`
2. Add the display name to the right list in `VENUE_GROUPS`
3. Run `bulk` — only the new venue will be fetched due to corpus caching

## Skill Update Rule

**Never delete existing patterns from `skill/references/*.md`.** Always accumulate — append new patterns, tag real data with `*(real ICLR 2024)*` or `*(real ICLR 2026)*` etc. Removing patterns breaks the calibration history.
