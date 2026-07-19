"""Deterministic venue-reference resolution for the generated PaperScope skill.

`manifest.json`'s `content.venues` map (built by `skill_builder.py`) is the *only* source
of truth this module resolves against -- there is no heuristic "similar venue" matching
and no fallback to any specific family (e.g. ICLR) for a venue that isn't listed. An
unresolvable query is `unsupported`, full stop; the caller (the skill's runtime
instructions) is expected to switch to `generic_uncalibrated` mode rather than guess.

Kept as plain, dependency-free Python so venue resolution stays testable outside of
prose -- see tests/test_venue_resolution.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GENERIC_UNCALIBRATED = "generic_uncalibrated"

STATUS_SUPPORTED = "supported"
STATUS_UNSUPPORTED = "unsupported"
STATUS_AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class VenueResolution:
    status: str  # one of STATUS_SUPPORTED / STATUS_UNSUPPORTED / STATUS_AMBIGUOUS
    family: str | None = None
    reference: str | None = None
    matched_candidates: tuple[str, ...] = field(default_factory=tuple)
    message: str = ""


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


def build_alias_index(venues: dict) -> dict[str, set[str]]:
    """Maps a normalized family name or alias -> the set of families it resolves to.

    A name mapping to more than one family is exactly what makes resolution ambiguous --
    computed once here so both `resolve_venue` and `find_alias_collisions` agree.
    """
    index: dict[str, set[str]] = {}

    def add(key: str, family: str) -> None:
        if not key:
            return
        index.setdefault(_normalize(key), set()).add(family)

    for family, entry in venues.items():
        add(family, family)
        for alias in entry.get("aliases", []):
            add(alias, family)
    return index


def resolve_venue(query: str, venues: dict) -> VenueResolution:
    """Resolve `query` against `venues` (== manifest["content"]["venues"]).

    Exact, case/whitespace-insensitive match only against a family's own key or one of
    its manifest-declared `aliases` -- never substring or fuzzy matching, and never a
    fallback to a specific family when nothing matches.
    """
    if not query or not query.strip():
        return VenueResolution(status=STATUS_UNSUPPORTED, message="empty venue query")

    index = build_alias_index(venues)
    matched_families = index.get(_normalize(query))

    if not matched_families:
        return VenueResolution(
            status=STATUS_UNSUPPORTED,
            message=(
                f"{query!r} is not a manifest-listed supported venue -- "
                f"use {GENERIC_UNCALIBRATED} mode"
            ),
        )
    if len(matched_families) > 1:
        return VenueResolution(
            status=STATUS_AMBIGUOUS,
            matched_candidates=tuple(sorted(matched_families)),
            message=(
                f"{query!r} matches multiple venue families {sorted(matched_families)} -- "
                "ask the user to disambiguate rather than guessing"
            ),
        )
    family = next(iter(matched_families))
    return VenueResolution(status=STATUS_SUPPORTED, family=family, reference=venues[family]["reference"])


def find_alias_collisions(venues: dict) -> list[str]:
    """Every name (family key or alias) that maps to more than one family -- a manifest
    with a nonempty result here is itself invalid (ambiguous by construction), distinct
    from `resolve_venue`'s per-query ambiguity at runtime.
    """
    index = build_alias_index(venues)
    return [
        f"{name!r} maps to multiple families: {sorted(fams)}"
        for name, fams in sorted(index.items())
        if len(fams) > 1
    ]
