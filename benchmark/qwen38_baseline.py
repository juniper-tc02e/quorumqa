"""Single-agent baseline using qwen3.8-max-preview via the Token Plan's
Anthropic-Messages-API-compatible endpoint. Standalone script, not wired
into lever_experiments.py or the core engine, because this model is only
reachable through a completely different API shape (Anthropic Messages,
x-api-key auth) and a completely different billing model (Token Plan
Credits, sliding 5h/7d quota windows) than every other model in this
project (OpenAI-compatible DashScope, per-token USD). Cost is reported in
raw input/output tokens only -- there is no published $/token rate for
Token Plan Credits, so no USD figure is computed or claimed.

Usage:
  python -m benchmark.qwen38_baseline --n 90 --seed 123 --concurrency 2
"""

import argparse
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from benchmark.load_gpqa import load_benchmark_set

load_dotenv(override=True)  # .env must win over a stale OS-level var -- see config.py

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

API_KEY = os.environ["QUORUMQA_TOKEN_PLAN_API_KEY"]
BASE_URL = os.environ.get("QUORUMQA_TOKEN_PLAN_BASE_URL", "https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic")
MESSAGES_URL = BASE_URL.rstrip("/") + "/v1/messages"
MODEL = "qwen3.8-max-preview"

SYSTEM = (
    "You are an expert answering a hard, graduate-level multiple-choice "
    "science question. Answer with your best single choice."
)


def _ask_once(question: str, choices: list[str]) -> tuple[str, dict]:
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        'Reply with JSON only, shape: {"letter": "A|B|C|D", "reasoning": "..."}\n'
        "Keep reasoning to at most 3 sentences."
    )
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": user}],
    }
    resp = requests.post(MESSAGES_URL, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    text = "\n".join(text_blocks)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"No JSON object found in response text: {text!r}")
    parsed = json.loads(match.group(0))
    letter = str(parsed.get("letter", "")).strip().upper()[:1]
    letter = letter if letter in "ABCD" else "A"

    usage = data.get("usage", {})
    return letter, usage


async def _run_one(item, semaphore):
    async with semaphore:
        start = time.monotonic()
        try:
            letter, usage = await asyncio.to_thread(_ask_once, item.question, item.choices)
        except Exception:
            log.exception("%s: DROPPED after unrecoverable error", item.question_id)
            return None
        correct = letter == item.correct_letter
        latency_s = time.monotonic() - start
        log.info(
            "%s: %s(%s) input_tokens=%s output_tokens=%s latency=%.1fs",
            item.question_id, letter, "correct" if correct else "wrong",
            usage.get("input_tokens"), usage.get("output_tokens"), latency_s,
        )
        return {
            "question_id": item.question_id,
            "subject": item.subject,
            "answer_letter": letter,
            "correct_letter": item.correct_letter,
            "correct": correct,
            "usage": usage,
            "latency_s": latency_s,
        }


async def main(n: int, seed: int, concurrency: int, out_path: Path, skip_huggingface: bool, retry_missing: bool):
    items = load_benchmark_set(n=n, seed=seed, skip_huggingface=skip_huggingface)
    log.info("Loaded %d benchmark questions (seed=%d) for qwen3.8-max-preview baseline", len(items), seed)

    existing = []
    if retry_missing and out_path.exists():
        existing = [json.loads(l) for l in out_path.open(encoding="utf-8")]
        done_ids = {r["question_id"] for r in existing}
        items = [it for it in items if it.question_id not in done_ids]
        log.info("Retry mode: %d already done, %d missing, retrying only the missing ones with the longer timeout", len(existing), len(items))

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [asyncio.ensure_future(_run_one(item, semaphore)) for item in items]
    results = list(existing)
    for coro in asyncio.as_completed(tasks):
        outcome = await coro
        if outcome is not None:
            results.append(outcome)

    dropped = (len(items) + len(existing)) - len(results)
    if dropped:
        log.warning("%d questions still dropped after this pass", dropped)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    log.info("Wrote %d results to %s", len(results), out_path)

    n_ok = len(results)
    correct = sum(1 for r in results if r["correct"])
    total_in = sum(r["usage"].get("input_tokens", 0) or 0 for r in results)
    total_out = sum(r["usage"].get("output_tokens", 0) or 0 for r in results)
    log.info(
        "SUMMARY n=%d accuracy=%.1f%% total_input_tokens=%d total_output_tokens=%d",
        n_ok, 100 * correct / n_ok if n_ok else 0, total_in, total_out,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--skip-huggingface", action="store_true")
    parser.add_argument("--retry-missing", action="store_true", help="Only re-run question_ids not already present in --out, appending to it")
    args = parser.parse_args()
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"qwen38_baseline_seed{args.seed}.jsonl"
    asyncio.run(main(args.n, args.seed, args.concurrency, out_path, args.skip_huggingface, args.retry_missing))
