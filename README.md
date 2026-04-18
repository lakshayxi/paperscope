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
pip install openreview-py requests
```

Set credentials:
```bash
export OPENREVIEW_USERNAME='your_openreview_email'
export OPENREVIEW_PASSWORD='your_openreview_password'
```

---

## Usage

### Fetch reviews for a venue
```bash
# Fetch 5 papers at a time (recommended — avoids rate limits)
python expl.py bulk --venues iclr --years 2024 --per-venue 5

# Fetch a single paper by URL
python expl.py forum --url "https://openreview.net/forum?id=XXXXX"

# Fetch all supported venues
python expl.py bulk
```

Fetched reviews are saved to `corpus_<venue>.json`. Re-runs automatically skip already-seen papers.

### Continuous batch fetching
```bash
python watch.py --venues iclr --years 2024 --per-venue 5 --interval 60
```

Fetches a new batch every 60 seconds, saves new papers to `corpus_iclr_inbox.json`, and waits until the inbox is cleared before fetching again.

### Review a single paper
```bash
python expl.py forum --url "https://openreview.net/forum?id=XXXXX" --save
```

---

## Installing the Skill

The `skill/` directory contains pre-built calibration files ready to use with Claude Code.

```bash
# Copy to Claude Code skills directory
cp -r skill/ ~/.claude/skills/paperscope
```

Then in any Claude Code session:
- *"Review this paper for ICLR 2025"*
- *"What score would this get at NeurIPS?"*
- *"Write a reviewer report targeting CVPR"*

The skill loads the venue-specific reference file before writing any review — scores, language patterns, hidden criteria, and rebuttal effectiveness are all calibrated to real data.

---

## Updating the Skill

The pre-built skill files in `skill/references/` are calibrated on real data. To improve them with fresh data:

1. Fetch new reviews: `python expl.py bulk --venues iclr --per-venue 5`
2. Share `corpus_iclr_inbox.json` with Claude
3. Claude updates `skill/references/iclr.md` with new real patterns
4. Delete inbox: `rm corpus_iclr_inbox.json`
5. Repeat

Reference files **accumulate** knowledge — patterns are never deleted unless consistently contradicted across many papers.

---

## Project Structure

```
paperscope/
├── expl.py              # Main CLI — fetch, analyze, build skill
├── watch.py             # Continuous batch watcher
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

## How calibration works

Each `references/<venue>.md` file contains:
- **Score calibration** — exact score labels and real-world acceptance meaning
- **Accept signals** — patterns that correlate with high scores, with real reviewer quotes
- **Reject signals** — patterns that correlate with rejection, with real reviewer quotes
- **Hidden criteria** — unwritten rules inferred from review data
- **Reviewer language** — exact phrases accept vs reject tier reviewers use
- **Year-over-year drift** — how standards shifted across years
- **Rebuttal effectiveness** — what actually moves scores vs what doesn't

---

## Contributing

To add a new venue:
1. Add a tuple to `VENUES` in `expl.py`: `("CONF YEAR", "venue.org/CONF/YEAR/Conference", "v2", "family")`
2. Add the display name to `VENUE_GROUPS`
3. Run `python expl.py bulk --venues <family>`

---

## Requirements

- Python 3.11+
- `openreview-py`
- `requests`
- OpenReview account (free at [openreview.net](https://openreview.net))

No Anthropic API key needed — skill files are pre-built and Claude updates them directly in conversation.
