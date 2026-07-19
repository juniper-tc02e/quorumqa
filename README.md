# QuorumQA -- a Qwen Cloud Agent Society

*Global AI Hackathon Series with Qwen Cloud -- Track 3: Agent Society*

Three cheap Qwen Solvers vote independently on a hard, "Google-proof"
science question. If they agree, done. If they split, a Skeptic, a
tool-using Verifier (via a real MCP server), and a Judge escalate and
resolve the disagreement -- and the Judge's ruling, including any unresolved
dissent, is recorded verbatim, never papered over into false consensus.

**Measured on the full 90-question GPQA-Diamond set (complete run, no
dropped questions):** organizing the same cheap models into a society lifts
accuracy from 58.9% (self-consistency@5 ensemble) to **78.9%** — closing
~78% of the gap to a thinking flagship agent (84.4%) at **11% lower cost**
than the flagship ($0.0213 vs $0.0240/question). The Judge overturned the
solver panel's plurality 14 times and was correct in 11 (78.6%).

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

## Deployment

The backend runs on Alibaba Cloud ECS and persists every deliberation
transcript to Alibaba Cloud OSS via [`deploy/oss_client.py`](deploy/oss_client.py)
-- see [`deploy/README.md`](deploy/README.md) for the full setup.

## License

MIT -- see [LICENSE](LICENSE).
