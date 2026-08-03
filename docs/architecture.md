# Architecture

QuorumQA is a Qwen Cloud Agent Society: three cheap Solvers vote on every
question in parallel; a Skeptic, a tool-using Verifier, and a Judge are
escalated to **only when the Solvers disagree**. Unanimous questions never
pay for the expensive roles at all -- that asymmetric escalation is the
entire **dollar**-cost story, not a benchmark trick layered on afterward.
**In tokens -- the unit that now bills -- the cascade is strictly more
expensive than one flagship call (8,690 vs 2,792/item on the TB-1 paired set,
seeds 1001/2311/3407, n=265; 9,013 vs 3,415 on the frozen n=90 seed-42
submission run), and against that call on identical items the full stack is
net +0, p=0.605 -- and net **-6** against the same budget spent on plain
sampling.** Two item sets, same quantity, both correct -- quote whichever
run the surrounding claim is about. See
[`FINDINGS-2026-08.md`](FINDINGS-2026-08.md).

```mermaid
flowchart TD
    Q[GPQA question] --> S1[Solver 1<br/>qwen3.6-flash]
    Q --> S2[Solver 2<br/>qwen3.6-flash]
    Q --> S3[Solver 3<br/>qwen3.6-flash]

    S1 --> D{Unanimous?}
    S2 --> D
    S3 --> D

    D -- yes --> F1[Final answer<br/>= plurality letter]

    D -- no, split --> K[Skeptic<br/>qwen3.6-flash<br/>attacks plurality's weakest step]
    D -- no, split --> V[Verifier<br/>qwen3.6-flash<br/>extracts checkable claims]

    V --> MCP[(MCP server<br/>lookup_constant / safe_calculate)]
    MCP --> V

    K --> J[Judge<br/>qwen3.7-max<br/>weighs arguments, not votes]
    V --> J

    J --> VC[Verdict Card<br/>final letter + decisive reasoning<br/>+ verbatim dissent]

    F1 --> OSS[(Alibaba Cloud OSS<br/>transcript persistence)]
    VC --> OSS

    OSS --> Dash[Streamlit dashboard<br/>on Alibaba Cloud ECS]
```

## Cost cascade (how the escalation is routed)

> **Superseded 2026-08 as a superiority claim.** In dollars under pre-Token-Plan
> pricing this routing was ~11% cheaper than calling the flagship on every
> question. **In tokens it is 2.64× more expensive** (9,013 vs 3,415/item on the
> n=90 seed-42 run the dollar figure comes from; 3.1×, 8,690 vs 2,792, on the
> TB-1 paired n=265 set), and
> on GPQA-Diamond the shipped config scores ~9 points *below* a single
> `qwen3.7-max` call. The full stack is net +0, p=0.605 against one flagship
> call on identical items. See [`FINDINGS-2026-08.md`](FINDINGS-2026-08.md).
> What follows describes the routing mechanism, which is unchanged.

| Role | Model | Thinking | Runs on |
|---|---|---|---|
| Solver seats 1-3 | `qwen3.6-flash` (cheapest) | off | every question |
| Skeptic | `qwen3.6-flash` (cheapest) | off | only on disagreement |
| Verifier | `qwen3.6-flash` (cheapest) | off | only on disagreement |
| Judge | `qwen3.7-max` (flagship) | **on** | only on disagreement |
| **Baseline** | `qwen3.7-max` (flagship) | on | every question, always |

Only **two** model tiers are actually billed in the frozen run: `qwen3.6-flash`
for all 270 solver, 34 skeptic and 53 verifier calls, and `qwen3.7-max` for the
34 judge calls and the 90 baseline calls. The judge is the same model as the
single-agent baseline, so the saving comes from *routing* that model to the
37.8% of questions that need it, not from avoiding it. An earlier design put a
`qwen3.7-plus` seat on the panel and in the skeptic role; it was dropped after
the 74-question run showed that seat was both the weakest solver and the source
of every JSON-malformation drop (see `SOLVER_MODELS` in `src/quorumqa/config.py`).

Two deliberate, measured design decisions here:

**Thinking mode is a budget, spent only at the adjudication layer.** Qwen3
hybrid models reason ("think") by default, billing reasoning tokens as
output. Our first live smoke run showed three *thinking* flash solvers
costing MORE than one thinking flagship call -- inverting the engine's
whole premise. So the fast-voter roles run with `enable_thinking: false`
(they exist to surface disagreement cheaply, not to deliberate), and the
one role whose output is a final ruling -- the Judge -- keeps full
reasoning. After this change, unanimous questions measured 2.5-6x cheaper
than the baseline call.

**The solver panel decorrelates through reasoning lens, not model family.**
The Heter-MAD finding from the deliberation literature (arXiv:2502.08788)
motivated an early attempt at mixing model families (flash/flash/plus) so
the three seats' failure modes would be less correlated -- but that plus
seat measured as the weakest solver and the source of every JSON-malformation
drop, and was dropped the same day (see the table above and `SOLVER_MODELS`
in `src/quorumqa/config.py`). Decorrelation now comes from three seats on
the same model, each answering through a distinct assigned reasoning lens
and its own temperature, instead of from mixing model families. A
unanimous-but-wrong panel is the one error this architecture cannot catch
(nothing triggers escalation), so decorrelating the seats is still what
protects the accuracy floor -- the mechanism just changed.

The benchmark (`benchmark/run_benchmark.py` + `benchmark/score.py`)
measures the actual blended cost-per-question and accuracy across a real
GPQA-Diamond sample -- see `benchmark/results/summary.md` after a run.

## Negotiation / conflict resolution

Disagreement isn't staged -- it's whatever the three independent Solvers
actually produce. When they split, the Skeptic must name the specific
inferential step it disputes (not a generic critique), the Verifier grounds
any numeric/factual claim through a real MCP tool call rather than letting
either side assert from memory, and the Judge is *instructed* to rule by
weighing arguments rather than re-counting votes -- with any unresolved
objection recorded verbatim as dissent rather than papered over.

> **What is measured, and what is not.** "Rules by weighing arguments, never by
> re-counting votes" was stated here as fact until 2026-08-03. It is a
> description of the **prompt** (`JUDGE_SYSTEM`: *"weigh ARGUMENTS, not
> headcounts; an unrefuted minority position beats a conforming majority"*),
> not a measured property of the behaviour.
>
> The evidence that it is not *merely* tallying: the Judge picks a letter **no
> solver picked** on 10.2% of escalations and is **right 83.3%** of those times
> (`benchmark/results/unanimous_gate_headroom.md`). That is a real,
> non-vote-counting behaviour.
>
> The evidence against the word *never*: the Judge re-confirms the plurality on
> **58.8%** of escalations (the false-escalation rate). Confirming the majority
> most of the time is exactly what vote-counting would also produce, and no
> measurement here separates the two. The honest claim is the prompt plus the
> off-slate rate — not "never".

## Escalation-integrity metrics

Beyond raw accuracy, `benchmark/score.py` reports:
- **Escalation rate** -- % of questions that needed the expensive chain.
- **False-escalation rate** -- % of escalations where the Judge just
  re-confirmed the plurality (paid for nothing new).
- **Overturn-and-correct rate** -- of the times the Judge overruled the
  plurality, how often that overrule was actually right.

These three numbers together are what make "the escalation is earning its
cost" a checked claim rather than an assumption.
