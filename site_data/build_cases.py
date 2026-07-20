"""Extract a curated, web-ready case set from the frozen n=90 benchmark run.

Output feeds the MagiAchiral public site: the hero deliberation replay, the
scoreboard, and the case gallery. Everything here is already public -- GPQA
questions, their public answer key, and our own model outputs. No credentials,
no infrastructure identifiers.
"""

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = ROOT / "benchmark" / "results" / "full_run2.jsonl"
OUT = pathlib.Path(__file__).resolve().parent / "cases.json"

# The hero replay: panel voted D, Judge overruled to C, C is correct.
HERO_ID = "recIj8lR4tuDgrHou"


def cost_of(calls):
    return round(sum(c.get("cost_usd", 0.0) for c in calls), 6)


def role_costs(calls):
    by_role = {}
    for c in calls:
        by_role[c["role"]] = round(by_role.get(c["role"], 0.0) + c.get("cost_usd", 0.0), 6)
    return by_role


def shape_case(rec):
    eng = rec["engine"]
    base = rec["baseline"]
    sc5 = rec["self_consistency5"]
    item = eng["item"]

    overturned = bool(eng.get("escalated")) and eng.get("final_letter") != eng.get("plurality_letter")

    if not eng.get("escalated"):
        verdict_kind = "unanimous"
    elif overturned:
        verdict_kind = "overruled"
    else:
        verdict_kind = "confirmed"

    return {
        "id": item["question_id"],
        "subject": item["subject"],
        "question": item["question"],
        "choices": item["choices"],
        "correct_letter": item["correct_letter"],
        "solvers": [
            {
                "letter": s["letter"],
                "confidence": s["confidence"],
                "reasoning": s["reasoning"],
                "lens": s["lens"],
            }
            for s in eng["solver_answers"]
        ],
        "plurality_letter": eng.get("plurality_letter"),
        "escalated": bool(eng.get("escalated")),
        "overturned": overturned,
        "verdict_kind": verdict_kind,
        "skeptic": eng.get("skeptic_rebuttal"),
        "verifier": eng.get("verifier_findings") or [],
        "verdict": eng.get("verdict"),
        "final_letter": eng.get("final_letter"),
        "correct": bool(eng.get("correct")),
        "false_escalation": bool(eng.get("false_escalation")),
        "cost_usd": cost_of(eng["calls"]),
        "cost_by_role": role_costs(eng["calls"]),
        "latency_s": round(eng.get("latency_s", 0.0), 2),
        "baseline": {
            "letter": base.get("answer_letter"),
            "correct": bool(base.get("correct")),
            "cost_usd": cost_of(base["calls"]),
            "latency_s": round(base.get("latency_s", 0.0), 2),
        },
        "self_consistency5": {
            "letter": sc5.get("answer_letter"),
            "correct": bool(sc5.get("correct")),
            "cost_usd": cost_of(sc5["calls"]),
        },
    }


def main():
    records = [json.loads(line) for line in RUN.open(encoding="utf-8")]
    cases = [shape_case(r) for r in records]
    n = len(cases)

    engine_correct = sum(c["correct"] for c in cases)
    base_correct = sum(c["baseline"]["correct"] for c in cases)
    sc5_correct = sum(c["self_consistency5"]["correct"] for c in cases)
    escalated = [c for c in cases if c["escalated"]]
    overturns = [c for c in cases if c["overturned"]]
    good_overturns = [c for c in overturns if c["correct"]]
    unanimous = [c for c in cases if not c["escalated"]]

    # The cases that most sharply justify the architecture: the expensive
    # flagship got it wrong where the cheap society got it right.
    beats_flagship = [c for c in cases if c["correct"] and not c["baseline"]["correct"]]

    stats = {
        "n": n,
        "accuracy": {
            "engine": round(100 * engine_correct / n, 1),
            "baseline": round(100 * base_correct / n, 1),
            "self_consistency5": round(100 * sc5_correct / n, 1),
        },
        "cost_per_question": {
            "engine": round(sum(c["cost_usd"] for c in cases) / n, 5),
            "baseline": round(sum(c["baseline"]["cost_usd"] for c in cases) / n, 5),
            "self_consistency5": round(sum(c["self_consistency5"]["cost_usd"] for c in cases) / n, 5),
        },
        "unanimous_cost_per_question": round(
            sum(c["cost_usd"] for c in unanimous) / max(len(unanimous), 1), 5
        ),
        "escalated_cost_per_question": round(
            sum(c["cost_usd"] for c in escalated) / max(len(escalated), 1), 5
        ),
        "escalation_rate": round(100 * len(escalated) / n, 1),
        "unanimous_rate": round(100 * len(unanimous) / n, 1),
        "false_escalation_rate": round(
            100 * sum(c["false_escalation"] for c in escalated) / max(len(escalated), 1), 1
        ),
        "overturns": len(overturns),
        "overturns_correct": len(good_overturns),
        "overturn_precision": round(100 * len(good_overturns) / max(len(overturns), 1), 1),
        "beats_flagship": len(beats_flagship),
        "median_latency_s": round(
            sorted(c["latency_s"] for c in cases)[n // 2], 2
        ),
        "subjects": dict(Counter(c["subject"] for c in cases).most_common()),
    }

    # Gallery: every overturn (including the three the Judge got wrong -- the
    # honest ones stay in), the flagship-beating cases, plus a representative
    # spread of confirmed escalations and cheap unanimous answers.
    picked, seen = [], set()

    def take(pool, limit=None):
        count = 0
        for c in pool:
            if c["id"] in seen:
                continue
            if limit is not None and count >= limit:
                break
            seen.add(c["id"])
            picked.append(c)
            count += 1

    take([c for c in cases if c["id"] == HERO_ID])
    take(overturns)
    take(sorted(beats_flagship, key=lambda c: -c["cost_usd"]), limit=6)
    take([c for c in escalated if not c["overturned"]], limit=6)
    take(sorted(unanimous, key=lambda c: c["cost_usd"]), limit=8)

    payload = {
        "generated_from": RUN.name,
        "stats": stats,
        "hero_case_id": HERO_ID,
        "cases": picked,
    }

    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.name}: {len(picked)} cases, {size_kb:.0f} KB")
    print(json.dumps(stats, indent=1))
    print("\nhero case present:", any(c["id"] == HERO_ID for c in picked))
    print("verdict kinds:", Counter(c["verdict_kind"] for c in picked).most_common())


if __name__ == "__main__":
    main()
