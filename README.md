# QuorumQA -- a Qwen Cloud Agent Society

*Global AI Hackathon Series with Qwen Cloud -- Track 3: Agent Society*

Three cheap Qwen Solvers vote independently on a hard, "Google-proof"
science question. If they agree, done. If they split, a Skeptic, a
tool-using Verifier (via a real MCP server), and a Judge escalate and
resolve the disagreement -- and the Judge's ruling, including any unresolved
dissent, is recorded verbatim, never papered over into false consensus.

Benchmarked against a single flagship-model baseline on the same GPQA-Diamond
questions: see [`docs/architecture.md`](docs/architecture.md) for the design
and [`benchmark/results/summary.md`](benchmark/results/summary.md) (after
running the benchmark) for the measured accuracy/cost numbers.

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
