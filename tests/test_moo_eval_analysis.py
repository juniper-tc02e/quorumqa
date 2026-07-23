"""Offline tests for benchmark/run_moo_eval.py's analysis logic (flat-best /
routed / oracle, per-bucket routing-vs-oracle, cost proxy). No live API
calls, no dataset downloads: exercises load_results/load_routes/analyze
against small hand-computed JSONL fixtures written to tmp_path, per
CLAUDE.md's TDD-over-re-running-benchmarks rule -- this is the gate before
the real (paid, multi-hour) blended-workload run.
"""

import json

from benchmark.run_moo_eval import PROFILE_NAMES, analyze


def _rec(question_id, bucket, subject, profile, correct, tokens):
    return {
        "question_id": question_id,
        "bucket": bucket,
        "subject": subject,
        "profile": profile,
        "correct": correct,
        "escalated": False,
        "total_tokens": tokens,
        "latency_s": 1.0,
        "result": {},
    }


def _write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _write_routes(path, budget, routes):
    path.write_text(
        json.dumps({"budget": budget, "routes": [
            {"question_id": qid, "bucket": b, "subject": s, "routed_profile": p} for qid, b, s, p in routes
        ]}),
        encoding="utf-8",
    )


def _all_profile_records(question_id, bucket, subject, correct_profile, tokens_by_profile=None):
    """One record per REGISTRY profile for `question_id`; only
    `correct_profile` (or none, if None) is marked correct."""
    tokens_by_profile = tokens_by_profile or {}
    return [
        _rec(question_id, bucket, subject, p, p == correct_profile, tokens_by_profile.get(p, 50))
        for p in PROFILE_NAMES
    ]


def test_flat_best_routed_oracle_hand_computed(tmp_path):
    jsonl_path = tmp_path / "eval.jsonl"
    routes_path = tmp_path / "eval.routes.json"

    records = []
    # q1: standard-tribunal correct (only). Routed correctly picks it -> hit.
    records += _all_profile_records("q1", "bucketA", "subjA", "standard-tribunal", {"standard-tribunal": 100})
    # q2: thinking_gate correct (only). Router mis-picks standard-tribunal -> miss.
    records += _all_profile_records("q2", "bucketA", "subjA", "thinking_gate")
    # q3: single-call correct (only). Routed correctly picks it -> hit.
    records += _all_profile_records("q3", "bucketB", "subjB", "single-call")
    _write_jsonl(jsonl_path, records)

    _write_routes(routes_path, "balanced", [
        ("q1", "bucketA", "subjA", "standard-tribunal"),
        ("q2", "bucketA", "subjA", "standard-tribunal"),
        ("q3", "bucketB", "subjB", "single-call"),
    ])

    summary = analyze(jsonl_path, routes_path)

    assert summary["n_common"] == 3
    assert summary["budget"] == "balanced"

    # Each of standard-tribunal/thinking_gate/single-call is correct on
    # exactly 1/3 questions; the rest are correct on 0/3.
    assert summary["profile_accuracy"]["standard-tribunal"] == 1 / 3
    assert summary["profile_accuracy"]["thinking_gate"] == 1 / 3
    assert summary["profile_accuracy"]["single-call"] == 1 / 3
    for p in ("stem-max", "flagship_panel", "rag_presolve", "rag_thinking_gate"):
        assert summary["profile_accuracy"][p] == 0.0

    assert summary["flat_best_accuracy"] == 1 / 3
    assert summary["flat_best_profile"] in ("standard-tribunal", "thinking_gate", "single-call")

    # Oracle: every question has SOME correct profile -> 100%.
    assert summary["oracle_accuracy"] == 1.0

    # Routed: q1 hit, q2 miss (router picked the wrong profile), q3 hit -> 2/3.
    assert summary["routed_accuracy"] == 2 / 3
    assert summary["routing_hit"] == 2
    assert summary["routing_miss"] == 1

    # Routing beats flat-best (2/3 vs 1/3) and closes exactly half the
    # flat-best -> oracle gap ((2/3 - 1/3) / (1 - 1/3) = 0.5).
    assert summary["routed_accuracy"] > summary["flat_best_accuracy"]
    gap_closed = (summary["routed_accuracy"] - summary["flat_best_accuracy"]) / (summary["oracle_accuracy"] - summary["flat_best_accuracy"])
    assert abs(gap_closed - 0.5) < 1e-9


def test_per_bucket_breakdown(tmp_path):
    jsonl_path = tmp_path / "eval.jsonl"
    routes_path = tmp_path / "eval.routes.json"

    records = []
    records += _all_profile_records("q1", "bucketA", "subjA", "standard-tribunal")
    records += _all_profile_records("q2", "bucketA", "subjA", "standard-tribunal")
    records += _all_profile_records("q3", "bucketB", "subjB", None)  # oracle can't solve q3 with any profile
    _write_jsonl(jsonl_path, records)

    _write_routes(routes_path, "cheap", [
        ("q1", "bucketA", "subjA", "standard-tribunal"),
        ("q2", "bucketA", "subjA", "standard-tribunal"),
        ("q3", "bucketB", "subjB", "single-call"),
    ])

    summary = analyze(jsonl_path, routes_path)
    bucket_a = summary["bucket_summary"]["bucketA"]
    bucket_b = summary["bucket_summary"]["bucketB"]

    assert bucket_a["n"] == 2
    assert bucket_a["oracle_accuracy"] == 1.0
    assert bucket_a["routed_accuracy"] == 1.0
    assert bucket_a["routed_profile_counts"] == {"standard-tribunal": 2}
    assert bucket_a["routing_hit"] == 2
    assert bucket_a["routing_miss"] == 0

    # No profile ever got q3 right -- oracle fails too, so this is NOT a
    # routing miss (nothing the router could have picked would have helped).
    assert bucket_b["n"] == 1
    assert bucket_b["oracle_accuracy"] == 0.0
    assert bucket_b["routed_accuracy"] == 0.0
    assert bucket_b["routing_hit"] == 0
    assert bucket_b["routing_miss"] == 0


def test_drops_excluded_from_common_but_counted(tmp_path):
    jsonl_path = tmp_path / "eval.jsonl"
    routes_path = tmp_path / "eval.routes.json"

    records = []
    records += _all_profile_records("q1", "bucketA", "subjA", "standard-tribunal")
    # q2: drop flagship_panel's record entirely (simulates an API failure).
    q2_records = [r for r in _all_profile_records("q2", "bucketA", "subjA", "thinking_gate") if r["profile"] != "flagship_panel"]
    records += q2_records
    _write_jsonl(jsonl_path, records)

    _write_routes(routes_path, "balanced", [
        ("q1", "bucketA", "subjA", "standard-tribunal"),
        ("q2", "bucketA", "subjA", "thinking_gate"),
    ])

    summary = analyze(jsonl_path, routes_path)
    # q2 is excluded from n_common because flagship_panel dropped for it --
    # only q1 is "apples-to-apples" complete across all 7 profiles.
    assert summary["n_common"] == 1
    assert summary["n_total_distinct_questions"] == 2
    assert summary["drop_counts"]["flagship_panel"] == 1
    assert summary["drop_counts"]["standard-tribunal"] == 0


def test_cost_proxy_average_tokens(tmp_path):
    jsonl_path = tmp_path / "eval.jsonl"
    routes_path = tmp_path / "eval.routes.json"

    records = []
    records += _all_profile_records("q1", "bucketA", "subjA", "standard-tribunal", {"standard-tribunal": 100, "flagship_panel": 900})
    records += _all_profile_records("q2", "bucketA", "subjA", "standard-tribunal", {"standard-tribunal": 200, "flagship_panel": 800})
    _write_jsonl(jsonl_path, records)

    _write_routes(routes_path, "balanced", [
        ("q1", "bucketA", "subjA", "standard-tribunal"),
        ("q2", "bucketA", "subjA", "standard-tribunal"),
    ])

    summary = analyze(jsonl_path, routes_path)
    assert summary["profile_avg_tokens"]["standard-tribunal"] == 150.0
    assert summary["profile_avg_tokens"]["flagship_panel"] == 850.0
    # Router picked the cheap profile both times.
    assert summary["routed_avg_tokens"] == 150.0
