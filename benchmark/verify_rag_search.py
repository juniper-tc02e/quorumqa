"""Manual verification harness for the G0.5 pre-embedded RAG index: runs 5
hardcoded STEM queries through the REAL `search_corpus` MCP tool (not a
bypass -- same function the Verifier's tool rack calls), prints top-3
titles+scores per query for a human relevance eyeball, and reports query
latency. See docs/rag-corpus-notes.md for how to read the results.

Usage:
  python benchmark/verify_rag_search.py --db-path benchmark/data/rag_index_preembedded.sqlite3
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

QUERIES = [
    "activation energy Arrhenius equation",
    "CRISPR Cas9 mechanism",
    "eigenvalue decomposition",
    "second law of thermodynamics entropy",
    "neural network backpropagation gradient descent",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("benchmark/data/rag_index_preembedded.sqlite3"))
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args(argv)

    os.environ["QUORUMQA_RAG_DB"] = str(args.db_path)
    # Import AFTER setting the env var -- mcp_server reads it per-call via
    # _rag_db_path(), but importing late also avoids paying for torch
    # import if argparse fails first.
    from quorumqa.tools.mcp_server import search_corpus

    print(f"DB: {args.db_path}")
    latencies = []
    for query in QUERIES:
        start = time.perf_counter()
        result = search_corpus(query, k=args.k)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        print(f"\nQuery: {query!r}")
        print(f"  ok={result['ok']} dense={result.get('dense')} latency={elapsed_ms:.1f}ms")
        if not result["ok"]:
            print(f"  ERROR: {result.get('error')}")
            continue
        for rank, r in enumerate(result["results"][: args.k], start=1):
            print(f"  {rank}. [{r['score']:.4f}] {r['title']}  ({r['source_url']})")

    print(f"\nLatency over {len(QUERIES)} queries: "
          f"min={min(latencies):.1f}ms max={max(latencies):.1f}ms "
          f"mean={sum(latencies)/len(latencies):.1f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
