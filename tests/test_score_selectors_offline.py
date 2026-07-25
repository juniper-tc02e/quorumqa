"""Offline tests for benchmark/score_selectors.py -- pure JSONL/dict mining,
no live API calls, no cost (mirrors benchmark/audit_selectors.py's own
zero-token posture).

Covers (per the task spec):
  (a) every selector's arithmetic on constructed pools -- plurality
      (including a tie), confidence_weighted and max_single_confidence
      each overriding plurality, the longest_reasoning junk control
      LOSING on a constructed pool, and oracle coverage.
  (b) the pool-size curve (k=1..K) via prefix subsampling.
  (c) McNemar values match the known constants (b=3,c=0 -> p=0.125;
      b=4,c=0 -> 0.0625; b=5,c=0 -> 0.03125), through THIS file's own row
      -> per_item -> discordant -> p wiring, not just the underlying
      analyze_panel_scaling function in isolation.
  (d) the S7 ship bar returns SHIP only when every clause passes, and
      DO NOT SHIP with a specific, identifiable reason per failing clause
      otherwise (net, discordant, McNemar significance, within-50%
      replication band, non-negative-per-seed -- tested individually).
  (e) the burned-seed guard (static BURNED_SEEDS list, dynamic
      original_audit_seeds() filename scan, and the pool_-prefix exclusion)
      raises on a burned seed and allows a fresh one.
  (f) main()'s CLI-level wiring: an end-to-end 3-seed ship-gate SHIP/DO NOT
      SHIP round trip, plus its guardrails (wrong pool count, burned seed,
      mismatched dataset).
"""

from __future__ import annotations

import json

import pytest

from benchmark.score_selectors import (
    BURNED_SEEDS,
    ORIGINAL_AUDIT_NET,
    assert_seeds_not_burned,
    discordant_vs_plurality,
    main,
    oracle_gap,
    original_audit_seeds,
    pool_size_curve,
    score_pool,
    score_row_at_k,
    selector_report,
    ship_gate_verdict,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _row(qid: str, correct_letter: str, samples: list[tuple[str, float, str]], dataset: str = "gpqa", seed: int = 900001) -> dict:
    """samples: [(letter, confidence, reasoning), ...] in sample_index order."""
    return {
        "question_id": qid,
        "item": {"question_id": qid, "question": "Q", "choices": ["c1", "c2", "c3", "c4"], "correct_letter": correct_letter},
        "dataset": dataset,
        "seed": seed,
        "samples": [
            {"question_id": qid, "sample_index": i, "letter": letter, "confidence": conf, "reasoning": reasoning}
            for i, (letter, conf, reasoning) in enumerate(samples)
        ],
    }


# ---------------------------------------------------------------------------
# (a) selector arithmetic
# ---------------------------------------------------------------------------


def test_plurality_majority_wins():
    row = _row("q1", "A", [("A", 0.5, "r"), ("A", 0.5, "r"), ("B", 0.5, "r")])
    rec = score_row_at_k(row, 3)
    assert rec["plurality"] is True


def test_plurality_tie_breaks_first_seen_matching_counter_most_common():
    # 1-1 tie: B appears first, so Counter.most_common(1) returns B (stable
    # sort on equal counts preserves insertion order) -- matches
    # audit_selectors.py's sel_plurality / the shipped engine's _plurality.
    row_gold_b = _row("q1", "B", [("B", 0.5, "r"), ("A", 0.5, "r")])
    row_gold_a = _row("q2", "A", [("B", 0.5, "r"), ("A", 0.5, "r")])
    assert score_row_at_k(row_gold_b, 2)["plurality"] is True
    assert score_row_at_k(row_gold_a, 2)["plurality"] is False


def test_confidence_weighted_can_override_plurality():
    # Two low-confidence A votes vs one very high-confidence B vote:
    # plurality (vote count) picks A, confidence_weighted (summed
    # confidence) picks B.
    row = _row("q1", "B", [("A", 0.3, "r"), ("A", 0.3, "r"), ("B", 0.9, "r")])
    rec = score_row_at_k(row, 3)
    assert rec["plurality"] is False
    assert rec["confidence_weighted"] is True


def test_max_single_confidence_can_override_plurality():
    row = _row("q1", "B", [("A", 0.5, "r"), ("A", 0.5, "r"), ("B", 0.99, "r")])
    rec = score_row_at_k(row, 3)
    assert rec["plurality"] is False
    assert rec["max_single_confidence"] is True


def test_longest_reasoning_junk_control_loses_on_a_constructed_pool():
    # Every row: plurality is correct (2 short-reasoning A votes beat 1
    # long-reasoning B vote), but longest_reasoning always picks the
    # long-reasoning B seat, which is wrong. This is the exact shape that
    # validates the whole comparison in benchmark/audit_selectors.py: a
    # junk selector should lose badly and consistently.
    rows = [
        _row(f"q{i}", "A", [("A", 0.5, "short"), ("A", 0.5, "short"), ("B", 0.5, "x" * 300)])
        for i in range(5)
    ]
    scored = score_pool(rows, k=3)
    assert scored["plurality_accuracy"] == 1.0
    assert scored["selectors"]["longest_reasoning"] == 0.0
    rep = selector_report(scored["per_item"], "longest_reasoning")
    assert rep["b"] == 0
    assert rep["c"] == 5
    assert rep["net"] == -5


def test_oracle_covers_even_when_plurality_is_wrong():
    row = _row("q1", "A", [("B", 0.5, "r"), ("B", 0.5, "r"), ("A", 0.5, "r")])
    rec = score_row_at_k(row, 3)
    assert rec["plurality"] is False
    assert rec["oracle"] is True


def test_prefix_k_cannot_exceed_logged_sample_count():
    row = _row("q1", "A", [("A", 0.5, "r")])
    with pytest.raises(ValueError, match="exceeds pool size"):
        score_row_at_k(row, 3)


# ---------------------------------------------------------------------------
# (b) pool-size curve (S6)
# ---------------------------------------------------------------------------


def test_pool_size_curve_accuracy_rises_as_k_grows():
    # k=1: only "B" seen -> wrong. k=2: 1-1 tie, B first-seen -> still
    # wrong. k=3: A takes the majority -> correct.
    row = _row("q1", "A", [("B", 0.5, "r"), ("A", 0.5, "r"), ("A", 0.5, "r")])
    curve = pool_size_curve([row], max_k=3)
    assert curve[1]["plurality_accuracy"] == 0.0
    assert curve[2]["plurality_accuracy"] == 0.0
    assert curve[3]["plurality_accuracy"] == 1.0


def test_pool_size_curve_defaults_max_k_to_smallest_row():
    rows = [
        _row("q1", "A", [("A", 0.5, "r")] * 5),
        _row("q2", "A", [("A", 0.5, "r")] * 3),
    ]
    curve = pool_size_curve(rows)
    assert max(curve.keys()) == 3  # capped by q2's shorter sample list


def test_oracle_gap_is_zero_when_plurality_always_covers_gold():
    row = _row("q1", "A", [("A", 0.5, "r"), ("A", 0.5, "r"), ("A", 0.5, "r")])
    scored = score_pool([row], k=3)
    gap = oracle_gap(scored, "plurality")
    assert gap["gap_pp"] == 0.0
    assert gap["gap_items"] == 0


# ---------------------------------------------------------------------------
# (c) McNemar values match the known constants, through this file's OWN
# row -> per_item -> discordant -> p wiring.
# ---------------------------------------------------------------------------


def _gain_row(qid: str) -> dict:
    """max_single_confidence right, plurality wrong (a McNemar "gain")."""
    return _row(qid, "B", [("A", 0.1, "r"), ("A", 0.1, "r"), ("B", 0.99, "r")])


@pytest.mark.parametrize("n_gain,expected_p", [(3, 0.125), (4, 0.0625), (5, 0.03125)])
def test_mcnemar_matches_known_constants_with_zero_losses(n_gain, expected_p):
    rows = [_gain_row(f"g{i}") for i in range(n_gain)]
    scored = score_pool(rows, k=3)
    rep = selector_report(scored["per_item"], "max_single_confidence")
    assert rep["b"] == n_gain
    assert rep["c"] == 0
    assert rep["p"] == pytest.approx(expected_p)


def test_discordant_vs_plurality_counts_gains_and_losses_separately():
    gain_rows = [_gain_row(f"g{i}") for i in range(2)]
    loss_rows = [_row(f"l{i}", "A", [("A", 0.1, "r"), ("A", 0.1, "r"), ("B", 0.99, "r")]) for i in range(3)]
    scored = score_pool(gain_rows + loss_rows, k=3)
    b, c = discordant_vs_plurality(scored["per_item"], "max_single_confidence")
    assert (b, c) == (2, 3)


# ---------------------------------------------------------------------------
# (d) S7 ship bar
# ---------------------------------------------------------------------------


def _seed_reports(specs):
    """specs: [(seed, b, c), ...] -> the per_seed_reports shape
    ship_gate_verdict expects."""
    return [{"seed": s, "b": b, "c": c} for s, b, c in specs]


def test_ship_gate_ships_when_every_clause_passes():
    reports = _seed_reports([(1, 15, 2), (2, 15, 2), (3, 15, 2)])  # pooled net=39, disc=51
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "GPQA-Diamond", reports)
    assert verdict == "SHIP"
    assert reasons == []
    assert stats["pooled_net"] == 39
    assert stats["pooled_discordant"] == 51
    assert stats["pooled_p"] < 0.05


def test_ship_gate_fails_on_net_too_low():
    reports = _seed_reports([(1, 2, 1), (2, 2, 1), (3, 2, 1)])  # pooled net=3 < 5
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "GPQA-Diamond", reports)
    assert verdict == "DO NOT SHIP"
    assert stats["pooled_net"] == 3
    assert any("net=" in r and "required +5" in r for r in reasons)


def test_ship_gate_fails_on_discordant_too_low():
    reports = _seed_reports([(1, 6, 0)])  # net=6 (>=5), discordant=6 (<12)
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "GPQA-Diamond", reports)
    assert verdict == "DO NOT SHIP"
    assert stats["pooled_discordant"] == 6
    assert any("discordant" in r for r in reasons)


def test_ship_gate_fails_on_mcnemar_not_significant():
    reports = _seed_reports([(1, 10, 8)])  # discordant=18 (ok), p not significant
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "GPQA-Diamond", reports)
    assert verdict == "DO NOT SHIP"
    assert stats["pooled_p"] > 0.05
    assert any("McNemar" in r and "0.05" in r for r in reasons)


def test_ship_gate_fails_on_effect_size_outside_band_isolated():
    # net=12, discordant=12, p tiny -- passes net/discordant/p and every
    # per-seed-non-negative check, fails ONLY the within-50%-of-55 band
    # ([27.5, 82.5]).
    reports = _seed_reports([(1, 6, 0), (2, 6, 0)])
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "GPQA-Diamond", reports)
    assert verdict == "DO NOT SHIP"
    assert stats["pooled_net"] == 12
    assert len(reasons) == 1
    assert "50%" in reasons[0]
    assert "outside" in reasons[0]


def test_ship_gate_fails_on_negative_individual_seed_isolated():
    # Pooled net=48 (within the [27.5, 82.5] band), discordant=76, p tiny --
    # passes every pooled clause, fails ONLY because seed 3's own net is
    # negative.
    reports = _seed_reports([(1, 30, 2), (2, 30, 2), (3, 2, 10)])
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "GPQA-Diamond", reports)
    assert verdict == "DO NOT SHIP"
    assert stats["pooled_net"] == 48
    assert len(reasons) == 1
    assert "negative" in reasons[0]
    assert "3" in reasons[0]


def test_ship_gate_fails_when_no_original_audit_reference_exists():
    # longest_reasoning was never a ship candidate in the S1 audit -- there
    # is no reference net to hold it to, and the gate must say so rather
    # than silently skip the clause.
    reports = _seed_reports([(1, 10, 0)])
    verdict, reasons, stats = ship_gate_verdict("longest_reasoning", "GPQA-Diamond", reports)
    assert verdict == "DO NOT SHIP"
    assert stats["original_net"] is None
    assert any("no original-audit reference" in r for r in reasons)


def test_original_audit_net_only_covers_the_two_benchmarks_that_cleared_s1():
    assert set(k[1] for k in ORIGINAL_AUDIT_NET) == {"GPQA-Diamond", "SuperGPQA-hard"}
    assert set(k[0] for k in ORIGINAL_AUDIT_NET) == {"confidence_weighted", "max_single_confidence"}


# ---------------------------------------------------------------------------
# (e) burned-seed guard
# ---------------------------------------------------------------------------


def test_assert_seeds_not_burned_raises_on_static_burned_seed(tmp_path):
    with pytest.raises(ValueError, match=r"burned"):
        assert_seeds_not_burned([42], results_dir=tmp_path)


def test_assert_seeds_not_burned_allows_a_fresh_seed(tmp_path):
    assert_seeds_not_burned([900001, 900002, 900003], results_dir=tmp_path)  # must not raise


def test_every_burned_seed_from_the_task_spec_is_present():
    assert BURNED_SEEDS == frozenset({42, 7, 123, 555, 777, 888, 271, 314, 217, 471, 606, 838})


def test_original_audit_seeds_scans_filenames_and_excludes_pool_prefix(tmp_path):
    (tmp_path / "lever_control_lexam_seed9001.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "pool_gpqa_cheap_k8_seed9002.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "no_seed_here.jsonl").write_text("", encoding="utf-8")

    seeds = original_audit_seeds(tmp_path)

    assert seeds == frozenset({9001})


def test_assert_seeds_not_burned_raises_on_dynamically_scanned_seed_but_not_on_pool_output(tmp_path):
    (tmp_path / "lever_control_lexam_seed9001.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "pool_gpqa_cheap_k8_seed9002.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match=r"burned"):
        assert_seeds_not_burned([9001], results_dir=tmp_path)
    assert_seeds_not_burned([9002], results_dir=tmp_path)  # only inside an excluded pool_ file -- must not raise


# ---------------------------------------------------------------------------
# (f) main() CLI-level wiring
# ---------------------------------------------------------------------------


def _samples_gain():
    return [("A", 0.1, "r"), ("A", 0.1, "r"), ("B", 0.99, "r")]  # plurality wrong, maxc right


def _seed_pool_rows(seed: int, n_gain: int, n_loss: int, dataset: str = "gpqa") -> list[dict]:
    rows = [_row(f"g{seed}_{i}", "B", _samples_gain(), dataset=dataset, seed=seed) for i in range(n_gain)]
    rows += [_row(f"l{seed}_{i}", "A", _samples_gain(), dataset=dataset, seed=seed) for i in range(n_loss)]
    return rows


def _write_pool(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_main_ship_gate_end_to_end_ships(tmp_path, capsys):
    seeds = [900011, 900012, 900013]
    paths = []
    for seed in seeds:
        p = tmp_path / f"pool_gpqa_cheap_k3_seed{seed}.jsonl"
        _write_pool(p, _seed_pool_rows(seed, n_gain=15, n_loss=2))
        paths.append(str(p))

    out_path = tmp_path / "report.json"
    rc = main(paths, "max_single_confidence", None, True, str(out_path))

    assert rc == 0
    captured = capsys.readouterr()
    assert ">>> SHIP" in captured.out

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ship_gate"]["verdict"] == "SHIP"
    assert payload["ship_gate"]["seeds"] == seeds


def test_main_ship_gate_end_to_end_do_not_ship(tmp_path, capsys):
    seeds = [900021, 900022, 900023]
    paths = []
    for seed in seeds:
        p = tmp_path / f"pool_gpqa_cheap_k3_seed{seed}.jsonl"
        _write_pool(p, _seed_pool_rows(seed, n_gain=1, n_loss=1))  # far too few discordant items
        paths.append(str(p))

    rc = main(paths, "max_single_confidence", None, True, None)

    assert rc == 1
    captured = capsys.readouterr()
    assert ">>> DO NOT SHIP" in captured.out


def test_main_ship_gate_requires_exactly_three_pools(tmp_path):
    p1 = tmp_path / "pool_gpqa_cheap_k3_seed900031.jsonl"
    p2 = tmp_path / "pool_gpqa_cheap_k3_seed900032.jsonl"
    _write_pool(p1, _seed_pool_rows(900031, 15, 2))
    _write_pool(p2, _seed_pool_rows(900032, 15, 2))

    with pytest.raises(ValueError, match="EXACTLY 3"):
        main([str(p1), str(p2)], "max_single_confidence", None, True, None)


def test_main_ship_gate_rejects_a_burned_seed(tmp_path):
    seeds = [42, 900041, 900042]  # 42 is burned
    paths = []
    for seed in seeds:
        p = tmp_path / f"pool_gpqa_cheap_k3_seed{seed}.jsonl"
        _write_pool(p, _seed_pool_rows(seed, 15, 2))
        paths.append(str(p))

    with pytest.raises(ValueError, match="burned"):
        main(paths, "max_single_confidence", None, True, None)


def test_main_ship_gate_rejects_mismatched_datasets(tmp_path):
    p1 = tmp_path / "pool_gpqa_cheap_k3_seed900051.jsonl"
    p2 = tmp_path / "pool_gpqa_cheap_k3_seed900052.jsonl"
    p3 = tmp_path / "pool_supergpqa_cheap_k3_seed900053.jsonl"
    _write_pool(p1, _seed_pool_rows(900051, 15, 2, dataset="gpqa"))
    _write_pool(p2, _seed_pool_rows(900052, 15, 2, dataset="gpqa"))
    _write_pool(p3, _seed_pool_rows(900053, 15, 2, dataset="supergpqa"))

    with pytest.raises(ValueError, match="SAME dataset"):
        main([str(p1), str(p2), str(p3)], "max_single_confidence", None, True, None)


def test_main_plain_scoring_mode_does_not_require_three_pools_or_check_seeds(tmp_path, capsys):
    # Plain scoring (no --ship-gate) is allowed on any number of pools,
    # including burned seeds -- only a SHIP verdict is guarded.
    p = tmp_path / "pool_gpqa_cheap_k3_seed42.jsonl"
    _write_pool(p, _seed_pool_rows(42, 15, 2))

    rc = main([str(p)], "max_single_confidence", None, False, None)

    assert rc == 0
    captured = capsys.readouterr()
    assert "POOL INVENTORY" in captured.out
