# Agent cost calibration -- measured, not estimated

Reproduce: `.venv/Scripts/python.exe benchmark/analyze_agent_costs.py`

**Zero paid tokens.** Log mining only, over Harbor job artifacts already
on disk from prior `harbor run` invocations. No Terminal-Bench task,
Harbor invocation, or model call was made to produce this report.

## 1. What was found

Search roots (Harbor `--jobs-dir` locations, deduplicated):
- `C:\Users\ONGJUN~1\AppData\Local\Temp\harbor_jobs` (does not exist on this machine)
- `C:\Users\ONGJUN~1\AppData\Local\Temp\harbor_jobs_pilot` (does not exist on this machine)
- `C:\Users\ONGJUN~1\AppData\Local\Temp\harbor_jobs_quorumqa` (does not exist on this machine)

In-repo search for stray agent/Harbor artifacts (`benchmark/results/`, anywhere else under the repo): **0 found** -- none. Harbor writes to its own --jobs-dir, never into this repo.

Harbor job directories found: 0

| job_name | root | agent | job max_turns | task dirs | included in cost stats |
|---|---|---|---|---|---|

QuorumQAAgent task trials recovered: **0**

**NO USABLE ARTIFACTS FOUND.** This is not a fabricated fallback: it means
none of the three known --jobs-dir locations exist on this machine right now
(most likely %TEMP% was cleared since the pilots ran). The cheapest way to
get a real number in that case is `docs/capability-roadmap.md`'s own A0'
calibration lever (4 tasks, k=1, ~0.5M tokens) -- there is no free substitute
once these temp artifacts are gone.
