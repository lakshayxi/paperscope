# Redistribution policy for the public data index

PaperScope's CI workflow commits a "public index" of fetched OpenReview data to the
`data` branch of this repository. This document explains what gets committed there,
what doesn't, and why -- based on OpenReview's actual terms, not assumption.

## What OpenReview's terms actually say

Per [openreview.net/legal/terms](https://openreview.net/legal/terms):

- **Reviews and comments**: by submitting a comment (which includes official reviews),
  the submitter agrees it is released under **CC BY 4.0** -- meaning redistribution with
  attribution is contractually permitted, not merely tolerated.
- **Metadata**: released under **CC0 1.0** where a copyright interest exists.
- **Papers/abstracts**: authors retain copyright; OpenReview receives a non-exclusive,
  perpetual, royalty-free distribution license. Not CC-BY by default -- varies by venue.
- No separate API terms of service exists; the API is covered by the same document. No
  explicit redistribution cap or numeric rate limit is stated (rate limits are described
  as discretionary, set by OpenReview editors as needed).

So full review-text redistribution with attribution is **technically permitted** under
CC BY 4.0. The excerpt cap this project applies is a **self-imposed norm**, not a legal
requirement -- see the reasoning below.

## Why we cap excerpts anyway

Existing NLP research built on bulk OpenReview data (PeerRead, ASAP-Review) has been
flagged by follow-up work (NLPeer, arXiv:2211.06651) as not clearly addressing licensing
and reviewer-consent norms for redistribution, even where the underlying license
technically permits it -- reviewers write under an expectation of venue-scoped
visibility, not necessarily "appears verbatim in a third-party dataset." NLPeer's own
more careful approach was to build from datasets that had already been deliberately
released for reuse, rather than bulk-redistributing OpenReview review text directly.

PaperScope follows the more conservative pattern:

- **Paper metadata** (title, abstract, authors, keywords) -- committed in full. Already
  public via arXiv/venue sites in the vast majority of cases, and CC0-covered.
- **Review/response text** -- committed only as a bounded excerpt
  (`PUBLIC_EXCERPT_MAX_CHARS`, currently 280 characters) plus a content hash and length,
  never the full text. The full text stays in the local-only corpus tier
  (`data/full/`), never committed anywhere, including this repo's `data` branch.
- **Every record keeps its `openreview.net/forum?id=...` URL** as the canonical source,
  satisfying CC BY 4.0 attribution and letting anyone read the full review at its
  original source rather than through a redistributed copy.
- **Numeric/structural fields** (ratings, confidence, decision, IDs, timestamps) are
  never excerpted -- they're data points, not prose being redistributed.

## Known limitations of this research

- The specific claim that NLPeer's paper states redistribution "might pose ethical and
  legal issues" was sourced from a secondary summary during research, not independently
  verified against the primary PDF. Treated as directional context, not a quoted legal
  finding.
- This covers OpenReview's platform-default terms. Individual venues can in principle
  configure different licensing on their invitations; this hasn't been audited
  per-venue.

## If this changes

If OpenReview's terms change, or a specific venue is found to use different licensing,
update `PUBLIC_EXCERPT_MAX_CHARS` in `src/paperscope/config.py` and this document
together -- don't let the constant drift out of sync with its justification.
