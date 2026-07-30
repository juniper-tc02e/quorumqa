# QuorumQA -- a Qwen Cloud Agent Society

*Global AI Hackathon Series with Qwen Cloud -- Track 3: Agent Society*

Three cheap Qwen Solvers vote independently on a hard, "Google-proof"
science question. If they agree, done. If they split, a Skeptic, a
tool-using Verifier (via a real MCP server), and a Judge escalate and
resolve the disagreement -- and the Judge's ruling, including any unresolved
dissent, is recorded verbatim, never papered over into false consensus.

**Measured on the full 90-question GPQA-Diamond set (complete run, no
dropped questions):** three cheap solvers, plus a flagship Judge called only
on the 37.8% of questions where they split, reach **78.9%** — against 58.9%
for those same cheap models run as a plain self-consistency@5 ensemble, and
84.4% for that flagship answering every question alone. So it closes ~78% of
the gap to the flagship at **11% lower cost** ($0.0213 vs $0.0240/question).
The saving comes from *routing* the expensive model to the questions that
need it, not from avoiding it: the Judge and the baseline are the same
`qwen3.7-max`. Every other role (3 solvers, Skeptic, Verifier) runs on
`qwen3.6-flash`. The Judge overturned the solver panel's plurality 14 times
and was correct in 11 (78.6%).

**Live site:** [magiachiral.com](https://magiachiral.com) replays real
recorded deliberations from this run, scoreboard and all 33 case transcripts
included.

See [`docs/architecture.md`](docs/architecture.md) for the design,
[`benchmark/results/summary.md`](benchmark/results/summary.md) for the full
scorecard, and [`docs/submission.md`](docs/submission.md) for the hackathon
submission text. Re-run everything yourself with the two commands in
"Quickstart" below -- the dataset answer key is public, nothing is
self-graded.

## Quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e . -r requirements.txt
cp .env.example .env        # fill in DASHSCOPE_API_KEY at minimum
```

Run the offline test suite (no API key, no cost -- validates the
orchestration logic and the MCP tool server):

```bash
pytest tests/ -v
```

Run the live dashboard:

```bash
streamlit run dashboard/app.py
```

Run the full benchmark (needs a real `DASHSCOPE_API_KEY`):

```bash
python -m benchmark.run_benchmark --n 90 --self-consistency
python -m benchmark.score benchmark/results/run.jsonl
```

## Project layout

```
src/quorumqa/
  config.py            role -> Qwen Cloud model tier mapping + pricing
  qwen_client.py        thin OpenAI-compatible DashScope client wrapper
  schemas.py             pydantic models for every role's output
  engine/                solver, skeptic, verifier, judge, orchestrator
  tools/                 the Verifier's MCP server + client (real MCP, not a shim)
benchmark/                GPQA-Diamond loader, benchmark runner, scorer
dashboard/                Streamlit UI: live question + benchmark scoreboard
deploy/                   Alibaba Cloud OSS client (proof of deployment) + ECS notes
docs/                     architecture diagram and design notes
```

## Research and findings

**→ [`docs/FINDINGS.md`](docs/FINDINGS.md) is the index to everything measured.**
**→ [`docs/figures/`](docs/figures/README.md) is the same story in nine figures.**

![Build progress in gap space](docs/figures/f01_build_progress_gap_space.png)

*Every benchmark's distance from a single `qwen3.7-max` call. x=0 is flagship
parity; open circle = the initial build, filled triangle = current best. The gap
closed on all four benchmarks where we built twice, and crossed zero on two.
Arrows appear only where a genuine second build exists — the other five
benchmarks ran one build and say so.*

The short version: deliberation pays if and only if solver errors decorrelate
into visible disagreement *and* the escalation mechanism fires on it. The
cheap-to-flagship gap (the unanimous-wrong rate) predicts whether that is even
possible — not benchmark difficulty, not baseline height, and not the subject
label. Medicine and hard science are both knowledge-and-reasoning multiple
choice, and they sit at opposite ends of that table.

That gap is **necessary but not sufficient**, and our own figures caught us
overstating it: LEXam has a 22% unanimous-wrong rate and still loses 6 points,
because there the missing ingredient is *knowledge*, not decorrelation. See
[`docs/figures/`](docs/figures/) — the "large gap, lever still lost" quadrant.

One result clears the 3-seed bar against a single `qwen3.7-max` call:
**+4.1 mean** on SuperGPQA-hard (pooled b=11, c=1, net +10, exact McNemar
p=0.0032, n=241 shared items) — at **~3.0× the measured tokens**, and with no
compute-matched control run, so it is "deliberation on top of the flagship
beats one call of it", not a free win. The other headline numbers are weaker
than this README used to imply, and the corrections are stated at the point of
use in [`docs/FINDINGS.md`](docs/FINDINGS.md):

- **Chemistry**: the missing matched baselines (seeds 217, 471) landed
  2026-07-29, completing a real 3-seed paired result — pooled net **+12,
  p=0.0059, clears the bar**. Not three uniform wins, though: seed 217 alone
  is +9 (p=0.002), seed 314 is +4 (noise), and **seed 471 is −1**. The 90.9%
  candidate-arm mean is unchanged; only the delta against a matched baseline
  was previously incomplete.
- **Retrieval +3.5** is measured against the **cheap-panel control**, not
  against a flagship call. Against a flagship call `rag_presolve` *loses* on
  every seed where the comparison is possible (−7.0 / −2.4 / −4.7).
- **GPQA-Diamond** matches-or-beats, marginal and inside noise.

The shipped submission config is 78.9% — *below* the flagship's 84.4%, at ~11%
lower cost; that was always a cost claim.

The largest artifact is the negative results:
**[`docs/negative-results.md`](docs/negative-results.md)** — 22 measured nulls
each with its mechanism, 6 methodological errors we caught in our own work, and
4 adjudicated contradictions between our own documents.

Prior work establishes multi-agent debate, aggregation, routing, judging, and
tool-assisted verification — this project builds on it rather than predating it.
What the null ledger contributes is a **source-traced, Qwen-specific record of
how one disagreement-triggered cascade behaves across multiple benchmarks**,
including where it fails, wastes escalation, or cannot observe unanimous errors:
one stack, one harness, one cost model, every claim traced to a committed
artifact. See [`docs/prior-art-and-positioning.md`](docs/prior-art-and-positioning.md)
for the component-level prior-art map and the claim boundaries.

## Deployment

The backend runs on Alibaba Cloud ECS and persists every deliberation
transcript to Alibaba Cloud OSS via [`deploy/oss_client.py`](deploy/oss_client.py)
-- see [`deploy/README.md`](deploy/README.md) for the full setup.

## License

MIT -- see [LICENSE](LICENSE).
