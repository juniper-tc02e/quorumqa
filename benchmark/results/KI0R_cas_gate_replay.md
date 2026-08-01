# KI-0R -- CAS-gate replay on the known-wrong and matched known-right pools

**docs/spec-sci1-and-knowledge-injection.md section 3.1.** Measures `p_check x y_detect` -- the fraction of items on which `cas_gate_check` emits a parseable relation AND local `sympy_check` returns `fail`, i.e. the fraction where `verified_gate_cas` would actually escalate.

**Pre-registered gate: product >= 0.311 on SuperGPQA-hard.** Below that, KI-1 Arm A (`verified_gate_cas`, 2.30M) and KI-2 (2.76M) are both dead -- the mechanical-verification branch of knowledge injection is closed for MC-science.

Matched unanimous-right sample seed: `analysis:8419`. Item selection reads this repo's own logged `correct` field; **no answer key was retrieved**.

## gpqa

| pool | n | checkable | parseable | unparseable | gate fires | p_check | y_detect | product |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| unanimous-**wrong** | 34 | 7 | 6 | 1 | 1 | 17.6% | 16.7% | 2.9% |
| unanimous-**right** | 34 | 11 | 10 | 1 | 5 | 29.4% | 50.0% | 14.7% |

**gpqa sensitivity product = 2.9%** (Wilson 95% CI [0.5%, 14.9%], 1/34).

- Against the 0.311 gate: **FAILS**.
- The entire 95% CI lies below the gate, so this is not a power problem.
- False-positive rate on unanimous-**right**: **14.7%** (5/34) -- these are items the gate would escalate that were already correct.

**Discrimination.** fired&wrong=1, fired&right=5 -- Fisher exact two-sided **p = 0.1974**.
- The gate fires **5.0x more often on CORRECT answers** than on wrong ones. It is anti-correlated with the thing it is supposed to detect.

## supergpqa

| pool | n | checkable | parseable | unparseable | gate fires | p_check | y_detect | product |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| unanimous-**wrong** | 151 | 63 | 55 | 8 | 24 | 36.4% | 43.6% | 15.9% |
| unanimous-**right** | 151 | 69 | 56 | 13 | 24 | 37.1% | 42.9% | 15.9% |

**supergpqa sensitivity product = 15.9%** (Wilson 95% CI [10.9%, 22.6%], 24/151).

- Against the 0.311 gate: **FAILS**.
- The entire 95% CI lies below the gate, so this is not a power problem.
- False-positive rate on unanimous-**right**: **15.9%** (24/151) -- these are items the gate would escalate that were already correct.

**Discrimination.** fired&wrong=24, fired&right=24 -- Fisher exact two-sided **p = 1.0000**.
- The firing rates on right and wrong items are **exactly equal**: the gate is a coin flip with respect to correctness.

## Cost

**391,741 tokens** (one `qwen3.6-flash` extraction call per item; `sympy_check` is offline and free).

Reproduce: `python -m benchmark.replay_cas_gate_on_wrong_pool --datasets gpqa,supergpqa --match-right-sample-seed 8419`