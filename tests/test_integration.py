"""Optional smoke test against a real, locally-fetched full-text corpus.

Not part of the default suite: the default suite runs entirely on the synthetic
fixtures in conftest.py so CI never depends on gitignored local data. This test only
runs when a developer points PAPERSCOPE_TEST_CORPUS at a real data/full/<family>.jsonl
file, e.g.:

    PAPERSCOPE_TEST_CORPUS=data/full/iclr.jsonl pytest -m integration
"""

import os
from pathlib import Path

import pytest

from paperscope import evidence as evidence_mod
from paperscope import statistics as statistics_mod
from paperscope import storage

pytestmark = pytest.mark.integration


def _real_corpus_path() -> Path | None:
    raw = os.environ.get("PAPERSCOPE_TEST_CORPUS")
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None


def test_smoke_against_real_local_corpus():
    path = _real_corpus_path()
    if path is None:
        pytest.skip("PAPERSCOPE_TEST_CORPUS is unset or does not point at an existing file")

    records = storage.load_corpus(path)
    assert records  # a real corpus file should never be empty

    corpus_hash = storage.corpus_hash(records)
    stats = statistics_mod.compute_all_statistics(records, corpus_hash=corpus_hash, generated_at="t0")
    assert len(stats) > 0

    if not evidence_mod.is_public_tier(records):
        items = evidence_mod.select_evidence(records, seed=42, corpus_hash=corpus_hash)
        evidence_mod.validate_evidence_bundle(items, records)  # must not raise
