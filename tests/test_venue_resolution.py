from paperscope import venue_resolution as vr


def _venues():
    return {
        "iclr": {"reference": "references/iclr.md", "aliases": ["International Conference on Learning Representations"]},
        "neurips": {"reference": "references/neurips.md", "aliases": ["NeurIPS", "NIPS"]},
    }


def test_exact_family_key_resolves():
    result = vr.resolve_venue("iclr", _venues())
    assert result.status == vr.STATUS_SUPPORTED
    assert result.family == "iclr"
    assert result.reference == "references/iclr.md"


def test_resolution_is_case_and_whitespace_insensitive():
    result = vr.resolve_venue("  IcLr  ", _venues())
    assert result.status == vr.STATUS_SUPPORTED
    assert result.family == "iclr"


def test_declared_alias_resolves():
    result = vr.resolve_venue("International Conference on Learning Representations", _venues())
    assert result.status == vr.STATUS_SUPPORTED
    assert result.family == "iclr"

    result2 = vr.resolve_venue("NIPS", _venues())
    assert result2.status == vr.STATUS_SUPPORTED
    assert result2.family == "neurips"


def test_undeclared_alias_does_not_resolve():
    # "NeurIPS Conference" is not a declared alias, and must not fuzzily match "neurips".
    result = vr.resolve_venue("NeurIPS Conference", _venues())
    assert result.status == vr.STATUS_UNSUPPORTED


def test_unknown_venue_is_unsupported_not_iclr():
    result = vr.resolve_venue("ACL 2025", _venues())
    assert result.status == vr.STATUS_UNSUPPORTED
    assert result.family is None
    assert result.reference is None


def test_unknown_venue_never_falls_back_to_any_family():
    for query in ("Totally Unknown Venue", "some random workshop", "xyz123"):
        result = vr.resolve_venue(query, _venues())
        assert result.status == vr.STATUS_UNSUPPORTED
        assert result.family is None


def test_empty_query_is_unsupported():
    result = vr.resolve_venue("", _venues())
    assert result.status == vr.STATUS_UNSUPPORTED
    result2 = vr.resolve_venue("   ", _venues())
    assert result2.status == vr.STATUS_UNSUPPORTED


def test_ambiguous_alias_across_families_is_rejected():
    venues = {
        "fam_a": {"reference": "references/fam_a.md", "aliases": ["Shared Conference Name"]},
        "fam_b": {"reference": "references/fam_b.md", "aliases": ["Shared Conference Name"]},
    }
    result = vr.resolve_venue("Shared Conference Name", venues)
    assert result.status == vr.STATUS_AMBIGUOUS
    assert result.matched_candidates == ("fam_a", "fam_b")
    assert result.family is None


def test_find_alias_collisions_detects_cross_family_collision():
    venues = {
        "fam_a": {"reference": "references/fam_a.md", "aliases": ["Shared Name"]},
        "fam_b": {"reference": "references/fam_b.md", "aliases": ["Shared Name"]},
    }
    collisions = vr.find_alias_collisions(venues)
    assert len(collisions) == 1
    assert "shared name" in collisions[0].lower()


def test_find_alias_collisions_empty_for_clean_manifest():
    assert vr.find_alias_collisions(_venues()) == []


def test_alias_cannot_collide_with_a_different_family_key():
    venues = {
        "iclr": {"reference": "references/iclr.md", "aliases": []},
        "neurips": {"reference": "references/neurips.md", "aliases": ["iclr"]},
    }
    collisions = vr.find_alias_collisions(venues)
    assert len(collisions) == 1
    result = vr.resolve_venue("iclr", venues)
    assert result.status == vr.STATUS_AMBIGUOUS
