"""Offline tests for benchmark/data/seed_registry.json (pre-flight P1,
docs/experiment-spec-book.md section 6.0).

The registry's job is to be the single source of truth for seed assignments
so colliding spec ids never silently merge result files. These tests pin it
against the CODE it must never drift from -- exactly the class of bug this
registry exists to prevent, and the bug this file's own first draft had
(seed 3 was transcribed from spec-book's prose, which has an error; the code
correctly omits it).
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "data" / "seed_registry.json"


def _load():
    with REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_registry_is_valid_json():
    _load()  # raises on malformed JSON


def test_burned_seeds_match_score_selectors_exactly():
    """The registry must track the ENFORCED list (score_selectors.BURNED_SEEDS),
    not spec-book's prose, which has a transcription error (seed 3)."""
    from benchmark.score_selectors import BURNED_SEEDS

    registry = _load()
    assert set(registry["burned_never_reusable"]) == set(BURNED_SEEDS)


def test_seed_3_is_deliberately_absent():
    """Regression pin for the exact discrepancy found while building this
    file: spec-book's prose lists seed 3 as burned; no result file anywhere
    uses it, and the dynamic original_audit_seeds() scan does not find it
    either. The registry follows the code, not the doc."""
    registry = _load()
    assert 3 not in registry["burned_never_reusable"]


def test_no_burned_seed_is_assigned_to_a_fresh_screen():
    """A block's own screen/extension seeds must not collide with the burned
    list -- that would defeat the registry's purpose."""
    registry = _load()
    burned = set(registry["burned_never_reusable"])
    for name, block in registry["blocks"].items():
        seeds = block.get("seeds")
        if not isinstance(seeds, dict):
            continue
        flat = []
        for v in seeds.values():
            if isinstance(v, list):
                flat.extend(x for x in v if isinstance(x, int))
            elif isinstance(v, int):
                flat.append(v)
        collision = set(flat) & burned
        assert not collision, f"block {name!r} assigns burned seed(s) {collision}"


def test_sel7_seeds_match_the_committed_s7_cli_example():
    """SEL-7's renumbered seeds (Q2 default) must match score_selectors.py's
    own documented CLI example -- both must move together."""
    registry = _load()
    assert registry["blocks"]["selection_pools"]["seeds"] == [411, 523, 631]


def test_session_additions_use_the_flagship_claims_own_seeds():
    """The compute-matched control is a PAIRED design -- it must run at
    exactly flagship_panel's seeds, not fresh ones."""
    registry = _load()
    cmc = registry["this_sessions_additions_not_in_the_original_spec_book"]["compute_matched_control"]
    assert set(cmc["seeds"]) == {42, 7, 123}


def test_chemistry_baseline_seeds_are_the_matching_pair():
    registry = _load()
    chem = registry["this_sessions_additions_not_in_the_original_spec_book"]["chemistry_matched_baselines"]
    assert set(chem["seeds"]) == {217, 471}
