"""QuorumQA dashboard: run one question live and watch the Agent Society
deliberate, or load a benchmark run and see the scoreboard vs. the
single-agent baseline.

    streamlit run dashboard/app.py
"""

import asyncio
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(_project_root))  # so `benchmark` (plain dir, not pip-installed) is importable

from quorumqa.baseline import solve_single_agent
from quorumqa.engine.orchestrator import run_question
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import GPQAItem
from quorumqa.tools.mcp_client import verifier_tool_session

from benchmark.score import render_markdown, summarize

st.set_page_config(page_title="QuorumQA", layout="wide")


async def _run_live(item: GPQAItem):
    client = QwenClient()
    baseline = await asyncio.to_thread(solve_single_agent, client, item)
    async with verifier_tool_session() as tool_session:
        engine_result = await run_question(client, tool_session, item)
    return baseline, engine_result


def _render_solver_cards(solver_answers):
    cols = st.columns(len(solver_answers))
    for col, ans in zip(cols, solver_answers):
        with col:
            st.markdown(f"**{ans.lens}**")
            st.metric("Answer", ans.letter, f"conf {ans.confidence:.2f}")
            st.caption(ans.reasoning)


def _render_result(baseline, result):
    st.subheader("Baseline (single flagship-tier call)")
    st.write(f"Answer: **{baseline.answer_letter}** -- "
             f"{'correct' if baseline.correct else 'incorrect'} -- "
             f"${baseline.total_cost_usd:.5f}")

    st.subheader("QuorumQA Solvers (independent, parallel)")
    _render_solver_cards(result.solver_answers)
    st.write(f"Plurality: **{result.plurality_letter}** -- "
             f"{'unanimous, no escalation' if not result.escalated else 'split -- escalating'}")

    if result.escalated:
        st.subheader("Skeptic rebuttal")
        st.write(f"Targeting **{result.skeptic_rebuttal.target_letter}**: "
                 f"{result.skeptic_rebuttal.disputed_step}")
        st.caption(result.skeptic_rebuttal.argument)

        if result.verifier_findings:
            st.subheader("Verifier (MCP tool calls)")
            for f in result.verifier_findings:
                icon = "✅" if f.supports_claim else "❌"
                st.write(f"{icon} `{f.tool_used}({f.tool_query})` -> {f.tool_result}")
                st.caption(f.claim)
        else:
            st.caption("Verifier found no checkable numeric/factual claims.")

        st.subheader("Verdict Card")
        v = result.verdict
        with st.container(border=True):
            st.markdown(f"### Final answer: {v.final_letter}  (confidence: {v.confidence})")
            st.write(v.decisive_reasoning)
            if v.dissent:
                st.warning(f"Unresolved dissent: {v.dissent}")
            if v.overturned_plurality:
                st.info(f"Overturned the {result.plurality_letter} plurality.")
            elif result.false_escalation:
                st.error("False escalation: Judge was invoked but only re-confirmed the plurality.")

    st.subheader("Scoreboard for this question")
    c1, c2, c3 = st.columns(3)
    c1.metric("QuorumQA answer", result.final_letter, "correct" if result.correct else "incorrect")
    c2.metric("QuorumQA cost", f"${result.total_cost_usd:.5f}",
              f"{result.total_cost_usd - baseline.total_cost_usd:+.5f} vs baseline")
    c3.metric("Escalated?", "yes" if result.escalated else "no")


def live_question_tab():
    st.header("Run one question live")
    question = st.text_area("Question", "A particle of mass m moves in a 1D infinite square well of width L. "
                                          "What is the ground-state energy?")
    choices = [
        st.text_input("Choice A", "h^2 / (8 m L^2)"),
        st.text_input("Choice B", "pi^2 h^2 / (2 m L^2)"),
        st.text_input("Choice C", "h^2 / (2 m L)"),
        st.text_input("Choice D", "2 h^2 / (m L^2)"),
    ]
    correct_letter = st.selectbox("Correct answer (for scoring the demo)", ["A", "B", "C", "D"])

    if st.button("Run QuorumQA", type="primary"):
        item = GPQAItem(question_id="live", question=question, choices=choices, correct_letter=correct_letter)
        with st.spinner("Solvers deliberating..."):
            baseline, result = asyncio.run(_run_live(item))
        _render_result(baseline, result)


def benchmark_tab():
    st.header("Benchmark scoreboard")
    default_path = "benchmark/results/full_run2.jsonl"  # the final n=90 complete run
    path_str = st.text_input("Results file (from run_benchmark.py)", default_path)
    path = Path(path_str)
    if not path.exists():
        st.info(f"No results file at {path}. Run:\n\n`python -m benchmark.run_benchmark --n 90`")
        return
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = summarize(records)
    st.markdown(render_markdown(summary))

    systems = ["baseline", "quorumqa"]
    accuracy = [summary["baseline_accuracy"], summary["engine_accuracy"]]
    cost = [summary["baseline_cost_per_question"], summary["engine_cost_per_question"]]
    if "self_consistency5_accuracy" in summary:
        systems.append("self-consistency@5")
        accuracy.append(summary["self_consistency5_accuracy"])
        cost.append(summary["self_consistency5_cost_per_question"])

    accuracy_df = pd.DataFrame({"accuracy": accuracy}, index=systems)
    cost_df = pd.DataFrame({"cost_per_question_usd": cost}, index=systems)
    st.bar_chart(accuracy_df)
    st.bar_chart(cost_df)


st.title("QuorumQA -- a Qwen Cloud Agent Society")
st.caption("Cheap parallel solvers vote; escalate to Skeptic/Verifier/Judge only on disagreement.")

tab1, tab2 = st.tabs(["Live question", "Benchmark scoreboard"])
with tab1:
    live_question_tab()
with tab2:
    benchmark_tab()
