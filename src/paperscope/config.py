"""Venue registry and shared path/schema defaults."""

from pathlib import Path

SCHEMA_VERSION = 1

# (display_name, venue_id, api_version, family)
# family is used for --family filtering (lowercase)
# api_version: "v1" = api.openreview.net, "v2" = api2.openreview.net
VENUES: list[tuple[str, str, str, str]] = [
    # -- ML / Theory ----------------------------------------------------------------
    ("ICLR 2026", "ICLR.cc/2026/Conference", "v2", "iclr"),
    ("ICLR 2025", "ICLR.cc/2025/Conference", "v2", "iclr"),
    ("ICLR 2024", "ICLR.cc/2024/Conference", "v2", "iclr"),
    ("ICLR 2023", "ICLR.cc/2023/Conference", "v2", "iclr"),
    ("NeurIPS 2025", "NeurIPS.cc/2025/Conference", "v2", "neurips"),
    ("NeurIPS 2024", "NeurIPS.cc/2024/Conference", "v2", "neurips"),
    ("NeurIPS 2023", "NeurIPS.cc/2023/Conference", "v2", "neurips"),
    ("ICML 2025", "ICML.cc/2025/Conference", "v2", "icml"),
    ("ICML 2024", "ICML.cc/2024/Conference", "v2", "icml"),
    ("ICML 2023", "ICML.cc/2023/Conference", "v1", "icml"),
    ("TMLR", "TMLR", "v1", "icml"),
    # -- NLP --------------------------------------------------------------------------
    ("ACL 2025", "aclweb.org/ACL/2025/Conference", "v2", "acl"),
    ("ACL 2024", "aclweb.org/ACL/2024/Conference", "v2", "acl"),
    ("ACL 2023", "aclweb.org/ACL/2023/Conference", "v2", "acl"),
    ("EMNLP 2025", "EMNLP/2025/Conference", "v2", "acl"),
    ("EMNLP 2024", "EMNLP/2024/Conference", "v2", "acl"),
    ("EMNLP 2023", "EMNLP/2023/Conference", "v2", "acl"),
    ("NAACL 2025", "NAACL/2025/Conference", "v2", "acl"),
    ("NAACL 2024", "NAACL/2024/Conference", "v2", "acl"),
    ("CoLM 2024", "colmweb.org/COLM/2024/Conference", "v2", "acl"),
    # -- Vision -------------------------------------------------------------------------
    ("CVPR 2025", "thecvf.com/CVPR/2025/Conference", "v2", "cvpr"),
    ("CVPR 2024", "thecvf.com/CVPR/2024/Conference", "v2", "cvpr"),
    ("CVPR 2023", "thecvf.com/CVPR/2023/Conference", "v2", "cvpr"),
    ("ICCV 2023", "thecvf.com/ICCV/2023/Conference", "v2", "cvpr"),
    ("ECCV 2024", "thecvf.com/ECCV/2024/Conference", "v2", "cvpr"),
    # -- AI General ----------------------------------------------------------------------
    ("AAAI 2026", "AAAI.org/2026/Conference", "v2", "aaai"),
    ("AAAI 2025", "AAAI.org/2025/Conference", "v2", "aaai"),
    ("AAAI 2024", "AAAI.org/2024/Conference", "v2", "aaai"),
    ("AAAI 2023", "AAAI.org/2023/Conference", "v2", "aaai"),
    ("IJCAI 2024", "ijcai.org/2024/Conference", "v2", "aaai"),
    ("IJCAI 2023", "ijcai.org/2023/Conference", "v2", "aaai"),
    # -- Data Mining -----------------------------------------------------------------------
    ("KDD 2024", "KDD.org/2024/Conference", "v2", "kdd"),
    ("KDD 2023", "KDD.org/2023/Conference", "v2", "kdd"),
]

VENUE_GROUPS: dict[str, list[str]] = {
    "iclr": ["ICLR 2023", "ICLR 2024", "ICLR 2025", "ICLR 2026"],
    "neurips": ["NeurIPS 2023", "NeurIPS 2024", "NeurIPS 2025"],
    "icml": ["ICML 2023", "ICML 2024", "ICML 2025", "TMLR"],
    "acl": [
        "ACL 2023", "ACL 2024", "ACL 2025",
        "EMNLP 2023", "EMNLP 2024", "EMNLP 2025",
        "NAACL 2024", "NAACL 2025", "CoLM 2024",
    ],
    "cvpr": ["CVPR 2023", "CVPR 2024", "CVPR 2025", "ICCV 2023", "ECCV 2024"],
    "aaai": [
        "AAAI 2023", "AAAI 2024", "AAAI 2025", "AAAI 2026",
        "IJCAI 2023", "IJCAI 2024",
    ],
    "kdd": ["KDD 2023", "KDD 2024"],
}

# Venue-years considered part of an "active" review cycle (subject to score/decision
# churn) as of the current calendar year. Update this as cycles close. Used by the
# refresh policy to decide which forums are worth re-checking rather than treated as
# finalized history.
ACTIVE_CYCLE_VENUE_NAMES: set[str] = {
    "ICLR 2026",
    "AAAI 2026",
}

DEFAULT_PER_VENUE = 20
DEFAULT_SEED = 42

# Refresh policy defaults (see refresh_policy.py)
REFRESH_MAX_ATTEMPTS = 6
REFRESH_BASE_INTERVAL_HOURS = 24
REFRESH_EXPIRY_DAYS = 180  # stop refreshing unresolved records this old, by default

# Public-index excerpt bound (see storage.py) -- conservative short-excerpt length for
# anything committed publicly (e.g. the `data` branch), pending explicit confirmation
# of OpenReview's redistribution terms (see docs/redistribution.md).
PUBLIC_EXCERPT_MAX_CHARS = 280

DATA_DIR = Path("data")
ARTIFACTS_DIR = Path("artifacts")

# Phase 3A -- statistics.py / evidence.py (see docs/statistics_and_evidence.md).
STATS_SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 1
# Evidence bundles are local-only (gitignored, under artifacts/), never committed --
# unlike PUBLIC_EXCERPT_MAX_CHARS this isn't a redistribution constraint, just a bound
# to keep bundles reviewable. Bounded, not full text, so bundle size stays predictable.
EVIDENCE_EXCERPT_MAX_CHARS = 600
DEFAULT_EVIDENCE_MAX_ITEMS = 60
DEFAULT_EVIDENCE_PER_BUCKET = 4

# Phase 3B -- generation.py (see docs/statistics_and_evidence.md and the Phase 3B
# checkpoint report for the manual stats -> evidence -> export-prompt -> validate ->
# render workflow).
GENERATION_SCHEMA_VERSION = 1

# Phase 4A -- skill_builder.py. SKILL_NAME must match the generated skill directory's
# SKILL.md `name:` frontmatter field exactly (see docs on Agent Skills naming rules).
SKILL_SCHEMA_VERSION = 1
SKILL_NAME = "paperscope-reviewer"


def is_active_cycle_venue(venue_family: str, venue_year: int | None) -> bool:
    """True if this family/year pair is one of the venues currently in an active review
    cycle (see ACTIVE_CYCLE_VENUE_NAMES) -- used by the refresh policy to decide whether
    an unresolved forum is still worth checking often, vs. treated as settled history.
    """
    if venue_year is None:
        return False
    for display_name, _venue_id, _api_version, family in VENUES:
        if family != venue_family:
            continue
        if display_name in ACTIVE_CYCLE_VENUE_NAMES and str(venue_year) in display_name:
            return True
    return False
