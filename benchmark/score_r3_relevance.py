"""Offline-buildable scoring harness for the W6 R3 relevance kill criterion
(docs/reasoning-supercharge-plan.md W6; the frozen instrument lives in
benchmark/r3_relevance_rubric.md, committed BEFORE any W6 pilot run).

What this does, end to end, when invoked for real (a live QwenClient, a
built rag_r3_targeted result JSONL, and the RAG index that produced it):

  1. Loads a rag_r3_targeted result JSONL (benchmark/lever_experiments.py's
     _build_output_row -- one JSON object per line, each carrying
     disputed_claim/r3_query_fired/r3_passages when R3 fired for that row).
  2. Filters to rows where R3 actually fired (r3_query_fired=true) and has
     at least one retrieved passage -- rows where the item never escalated,
     or R3's retrieval failed/found nothing, have nothing to score.
  3. For each such row, re-opens the SAME RAG index the run used (rag_db
     from the row) and re-retrieves top-RAG_R3_K passages for that row's
     disputed_claim -- the R3 retrieval hop (benchmark.lever_experiments.
     retrieve_r3_evidence) is a deterministic function of (index,
     disputed_claim, k), so this reproduces the exact passage TEXT the
     original run saw without ever having to persist full passage text in
     the (deliberately lean, titles/ids/scores-only) output row.
  4. Scores each (disputed_claim, passage) pair with the frozen rubric
     (benchmark/r3_relevance_rubric.md), majority-of-3 at temperature 0.
  5. Reports the pooled off-topic rate against the pre-registered 50%
     threshold and which verdict (kill / no-kill) it implies.

The PROMPT STRING used here is READ VERBATIM from r3_relevance_rubric.md at
runtime (see load_rubric_prompt/rubric_system_prompt/build_rubric_user_
prompt below) -- never hand-duplicated -- so this script can never silently
drift from the frozen, pre-registered instrument.

Usage (live, once a rag_r3_targeted result file + its RAG index exist):
  python -m benchmark.score_r3_relevance --input benchmark/results/lever_rag_r3_targeted_supergpqa_seed<SEED>.jsonl

Offline (no live API calls): every function below is independently unit-
tested with a fake client in tests/test_lever_rag_r3_offline.py -- this
module makes no network call at import time.
"""

import argparse
import json
import logging
from pathlib import Path

from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import QwenClient

log = logging.getLogger(__name__)

RUBRIC_PATH = Path(__file__).resolve().parent / "r3_relevance_rubric.md"
_PROMPT_START_MARKER = "<!-- RUBRIC_PROMPT_START -->"
_PROMPT_END_MARKER = "<!-- RUBRIC_PROMPT_END -->"
_CLAIM_TOKEN = "<<CLAIM>>"
_PASSAGE_TOKEN = "<<PASSAGE>>"

# Pre-registered per docs/reasoning-supercharge-plan.md W6: "> 50% of R3
# queries judged off-topic ... " -- kept as a module constant (not
# hardcoded inline at the report site) so a test can assert the harness's
# threshold matches the plan's stated number.
OFF_TOPIC_KILL_THRESHOLD = 0.50
MAJORITY_N = 3  # majority-of-3, per the frozen rubric's Aggregation section


def load_rubric_prompt(rubric_path: Path = RUBRIC_PATH) -> str:
    """Reads the frozen rubric prompt VERBATIM from r3_relevance_rubric.md
    (the block between RUBRIC_PROMPT_START/RUBRIC_PROMPT_END markers) --
    this harness must never hand-duplicate a copy of that text that could
    drift from the frozen, pre-registered instrument; see the rubric
    file's "Freeze notice" section."""
    text = rubric_path.read_text(encoding="utf-8")
    if _PROMPT_START_MARKER not in text or _PROMPT_END_MARKER not in text:
        raise ValueError(
            f"{rubric_path} is missing the RUBRIC_PROMPT_START/RUBRIC_PROMPT_END markers -- "
            "the frozen prompt block could not be located."
        )
    start = text.index(_PROMPT_START_MARKER) + len(_PROMPT_START_MARKER)
    end = text.index(_PROMPT_END_MARKER)
    return text[start:end].strip("\n")


def split_system_user(raw_prompt: str) -> tuple[str, str]:
    """Splits the frozen prompt block (as returned by load_rubric_prompt)
    into its SYSTEM: and USER: sections. The USER section still contains
    the raw <<CLAIM>>/<<PASSAGE>> placeholder tokens -- see
    build_rubric_user_prompt for substitution."""
    system_marker, user_marker = "SYSTEM:", "USER:"
    if system_marker not in raw_prompt or user_marker not in raw_prompt:
        raise ValueError("Rubric prompt is missing SYSTEM:/USER: section markers.")
    system_start = raw_prompt.index(system_marker) + len(system_marker)
    user_start = raw_prompt.index(user_marker)
    system = raw_prompt[system_start:user_start].strip()
    user_template = raw_prompt[user_start + len(user_marker):].strip()
    return system, user_template


def rubric_system_prompt(rubric_path: Path = RUBRIC_PATH) -> str:
    system, _user_template = split_system_user(load_rubric_prompt(rubric_path))
    return system


def build_rubric_user_prompt(claim: str, passage: str, rubric_path: Path = RUBRIC_PATH) -> str:
    """Fills the frozen USER template's <<CLAIM>>/<<PASSAGE>> tokens with
    the actual disputed claim and passage text -- BLINDED by construction:
    the template (read straight from the frozen rubric file) contains
    nothing about the original exam question or answer choices, and this
    function never adds any."""
    _system, user_template = split_system_user(load_rubric_prompt(rubric_path))
    return user_template.replace(_CLAIM_TOKEN, claim).replace(_PASSAGE_TOKEN, passage)


def score_passage_relevance(
    client, disputed_claim: str, passage_text: str, n: int = MAJORITY_N, rubric_path: Path = RUBRIC_PATH,
) -> tuple[bool, list[dict]]:
    """Runs the frozen rubric check `n` times (default 3, majority vote) at
    temperature 0 for ONE (disputed_claim, passage) pair. Returns
    (on_topic_majority, votes) -- votes is the list of individual
    {"on_topic": bool, "reason": str} dicts, so callers/tests can inspect
    the raw votes as well as the aggregated verdict."""
    system = rubric_system_prompt(rubric_path)
    user = build_rubric_user_prompt(disputed_claim, passage_text, rubric_path)
    votes = []
    for _ in range(n):
        result = client.chat_json(
            model=MECHANICAL_MODEL, system=system, user=user, role="r3_relevance",
            thinking=False, temperature=0.0, retries=2,
        )
        votes.append({"on_topic": bool(result.data.get("on_topic", False)), "reason": str(result.data.get("reason", ""))})
    on_topic_votes = sum(1 for v in votes if v["on_topic"])
    majority_on_topic = on_topic_votes >= (n // 2 + 1)
    return majority_on_topic, votes


def load_r3_records(input_path: Path) -> list[dict]:
    """Loads a rag_r3_targeted result JSONL (one JSON object per line, the
    shape benchmark.lever_experiments._build_output_row writes)."""
    records = []
    with input_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_r3_claim_passage_rows(records: list[dict]) -> list[dict]:
    """Filters a loaded rag_r3_targeted result set down to the rows worth
    scoring: R3 must have actually fired (r3_query_fired=true) AND
    retrieved at least one passage. Returns one dict per row with the
    fields the scoring/re-retrieval step needs (disputed_claim, the logged
    r3_passages -- titles/ids/scores only, per the output row's lean-log
    design -- and the rag_db path needed to re-open the same index for
    full-text re-retrieval)."""
    rows = []
    for row in records:
        if row.get("lever") != "rag_r3_targeted":
            continue
        if not row.get("r3_query_fired"):
            continue
        passages = row.get("r3_passages") or []
        if not passages:
            continue
        rows.append({
            "question_id": (row.get("engine") or {}).get("item", {}).get("question_id"),
            "disputed_claim": row.get("disputed_claim"),
            "r3_passages": passages,
            "rag_db": row.get("rag_db"),
        })
    return rows


def score_r3_result_file(client, records: list[dict], retrieve_passage_text) -> dict:
    """The core scoring loop, decoupled from HOW passage text is fetched
    (retrieve_passage_text(disputed_claim, logged_passage) -> str) so it
    can be exercised offline with a fake lookup, and for real with a
    function that re-queries the live RAG index. Returns a report dict:
    {"scored": [...], "total_passages": int, "off_topic_count": int,
    "off_topic_rate": float, "killed": bool}."""
    rows = extract_r3_claim_passage_rows(records)
    scored = []
    for row in rows:
        claim = row["disputed_claim"]
        if not claim:
            continue
        for passage in row["r3_passages"]:
            passage_text = retrieve_passage_text(claim, passage)
            if passage_text is None:
                log.warning("score_r3_relevance: could not resolve passage text for %r -- skipping", passage)
                continue
            on_topic, votes = score_passage_relevance(client, claim, passage_text)
            scored.append({
                "question_id": row["question_id"], "disputed_claim": claim,
                "passage_title": passage.get("title"), "on_topic": on_topic, "votes": votes,
            })

    total = len(scored)
    off_topic_count = sum(1 for s in scored if not s["on_topic"])
    off_topic_rate = (off_topic_count / total) if total else 0.0
    return {
        "scored": scored,
        "total_passages": total,
        "off_topic_count": off_topic_count,
        "off_topic_rate": off_topic_rate,
        "killed": total > 0 and off_topic_rate > OFF_TOPIC_KILL_THRESHOLD,
        "threshold": OFF_TOPIC_KILL_THRESHOLD,
    }


def _live_passage_text_lookup(rag_db_path: str, rag_k: int):
    """Builds a retrieve_passage_text callable that re-opens the SAME RAG
    index the rag_r3_targeted run used and re-retrieves top-k passages for
    a disputed_claim (byte-identical query to the original R3 retrieval --
    see benchmark.lever_experiments.retrieve_r3_evidence), matching the
    logged passage by title to recover its full text. Only imports
    benchmark.lever_experiments lazily (inside this function) so this
    module stays importable without the rag extras installed."""
    from benchmark import lever_experiments

    rag_config = lever_experiments.build_rag_presolve_config(rag_db_path, k=rag_k)

    def _lookup(claim: str, logged_passage: dict):
        results, fired = lever_experiments.retrieve_r3_evidence(rag_config, claim, k=rag_k)
        if not fired:
            return None
        title = logged_passage.get("title")
        for r in results:
            if r.get("title") == title:
                return r.get("text")
        # Title no longer among the top-k (index/content drift since the
        # original run) -- fall back to the top result rather than
        # dropping the passage silently, so scoring can still proceed.
        return results[0].get("text") if results else None

    return _lookup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=str, help="rag_r3_targeted result JSONL path")
    parser.add_argument("--rag-k", type=int, default=None, help="Override R3's retrieval k (default: RAG_R3_K from lever_experiments)")
    args = parser.parse_args(argv)

    from benchmark import lever_experiments

    records = load_r3_records(Path(args.input))
    rows = extract_r3_claim_passage_rows(records)
    if not rows:
        log.warning("No rag_r3_targeted rows with r3_query_fired=true and retrieved passages found in %s", args.input)
        print(json.dumps({"total_passages": 0, "off_topic_rate": 0.0, "killed": False, "threshold": OFF_TOPIC_KILL_THRESHOLD}))
        return

    rag_db_path = rows[0]["rag_db"]
    rag_k = args.rag_k if args.rag_k is not None else lever_experiments.RAG_R3_K
    retrieve_passage_text = _live_passage_text_lookup(rag_db_path, rag_k)

    client = QwenClient()
    report = score_r3_result_file(client, records, retrieve_passage_text)
    print(json.dumps({
        "total_passages": report["total_passages"],
        "off_topic_count": report["off_topic_count"],
        "off_topic_rate": report["off_topic_rate"],
        "threshold": report["threshold"],
        "killed": report["killed"],
    }, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
