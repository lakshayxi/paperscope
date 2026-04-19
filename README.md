# PaperScope

A venue-calibrated ML paper reviewer trained on real peer reviews from OpenReview (2023–2026).

PaperScope fetches real reviews from top ML/NLP/Vision venues, builds calibration reference files per venue, and packages them as a Claude Code skill — so when you ask Claude to review a paper, it reviews like an actual ICLR or NeurIPS reviewer, not a generic AI assistant.

---

## What it does

1. **Fetches** real peer reviews from OpenReview across ~35 ML/NLP/Vision venues (ICLR, NeurIPS, ICML, CVPR, ACL, AAAI, KDD, and more)
2. **Builds** venue calibration files — real score distributions, real accept/reject language, real hidden criteria
3. **Packages** everything as a Claude Code skill (`skill/`) that can be installed and used directly

---

## Supported Venues

| Group | Venues |
|---|---|
| ICLR | 2023, 2024, 2025, 2026 |
| NeurIPS | 2023, 2024, 2025 |
| ICML / TMLR | 2023, 2024, 2025 + TMLR rolling |
| CVPR / ICCV / ECCV | CVPR 2023–2025, ICCV 2023, ECCV 2024 |
| ACL / EMNLP / NAACL | 2023–2025 |
| AAAI / IJCAI | 2023–2026 |
| KDD | 2023, 2024 |

---

## Setup

```bash
git clone https://github.com/lakshayxi/paperscope
cd paperscope
pip install openreview-py
```

Set credentials (free account at [openreview.net](https://openreview.net)):
```bash
export OPENREVIEW_USERNAME='your_openreview_email'
export OPENREVIEW_PASSWORD='your_openreview_password'
```

---

## Usage

### Fetch reviews for a venue
```bash
# Fetch 20 papers at a time
python expl.py bulk --venues iclr --years 2024 --per-venue 20

# Fetch a specific year
python expl.py bulk --venues neurips --years 2024 --per-venue 20

# Fetch a single paper by URL
python expl.py forum --url "https://openreview.net/forum?id=XXXXX"

# Fetch all supported venues
python expl.py bulk
```

Fetched reviews are saved to `corpus_<venue>.json`. Re-runs automatically skip already-seen papers — seen forum IDs are tracked in `.seen_*.json` files per venue.

Each run also writes a `corpus_<venue>_inbox.json` containing only the **new** reviews from that batch. This is what you share with Claude to update the skill.

---

## Installing the Skill

The `skill/` directory contains pre-built calibration files ready to use with Claude Code.

To install, copy the skill folder into Claude Code's skills directory:

```bash
cp -r skill/ ~/Library/Application\ Support/Claude/skills/paperscope
```

> The exact skills path may vary by OS and Claude Code version. Check your Claude Code settings for the correct location, or place the folder wherever Claude Code looks for custom skills.

Then in any Claude Code session:
- *"Review this paper for ICLR 2025"*
- *"What score would this get at NeurIPS?"*
- *"Write a reviewer report targeting CVPR"*
- *"Is this paper ready to submit to ICLR 2026?"*

The skill automatically detects the venue and loads the corresponding reference file — scores, language patterns, hidden criteria, and rebuttal effectiveness are all calibrated to real data.

---

## Updating the Skill (the learning loop)

The pre-built skill files in `skill/references/` are calibrated on real data. To improve them with fresh data:

1. Fetch a new batch: `python expl.py bulk --venues iclr --years 2026 --per-venue 20`
2. Tell Claude: **"inbox ready"** — Claude reads `corpus_iclr_inbox.json`
3. Claude updates `skill/references/iclr.md` with new patterns tagged `*(real ICLR 2026)*`
4. Delete the inbox: `rm corpus_iclr_inbox.json`
5. Repeat

Reference files **accumulate** knowledge — patterns are never deleted, only added and tagged by year. This means you can ask Claude to review a paper specifically against 2026 trends vs. 2024 patterns.

---

## How calibration works

Each `references/<venue>.md` file contains:

- **Score calibration** — exact score labels (e.g. ICLR's "6 = marginally above acceptance threshold") and what they mean in practice
- **Accept signals** — patterns that correlate with high scores, backed by real reviewer quotes
- **Reject signals** — patterns that reliably cause rejection, with exact quotes showing how reviewers phrase them
- **Hidden criteria** — unwritten rules inferred from review data (e.g. ICLR penalizes complexity relative to gain more than any other venue)
- **Reviewer language** — exact phrases accept vs. reject tier reviewers use
- **Year-over-year drift** — how standards shifted across years (e.g. 2025→2026: high reviewer score variance now hurts more than before)
- **Rebuttal effectiveness** — what actually moves scores vs. what gets ignored

---

## Project Structure

```
paperscope/
├── expl.py              # Main CLI — fetch, analyze, build skill
├── skill/
│   ├── SKILL.md         # Claude Code skill definition
│   └── references/
│       ├── iclr.md      # ICLR calibration (2023–2026)
│       ├── neurips.md   # NeurIPS calibration (2023–2025)
│       ├── icml.md      # ICML + TMLR calibration
│       └── cvpr.md      # CVPR / ICCV / ECCV calibration
└── README.md
```

---

## Adding a New Venue

1. Add a tuple to `VENUES` in `expl.py`: `("CONF YEAR", "venue.org/CONF/YEAR/Conference", "v2", "Official_Review")`
2. Add the display name to the right list in `VENUE_GROUPS`
3. Run `python expl.py bulk --venues <family>` — corpus caching means only the new venue will be fetched

---

## Requirements

- Python 3.11+
- `openreview-py`
- OpenReview account (free at [openreview.net](https://openreview.net))

No Anthropic API key needed — skill files are pre-built and Claude updates them directly in conversation.
