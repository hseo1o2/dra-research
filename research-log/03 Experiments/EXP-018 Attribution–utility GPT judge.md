---
type: experiment
id: EXP-018
date: 2026-08-04
status: completed
project: DRA-personalization-attribution
rq: RQ-Utility — Does stage Acc@1 track personalization quality?
---

# EXP-018 Attribution–utility GPT judge

## Pre-run lock

- Objective: Measure association between frozen Solar hard-neg stage Acc and
  end-to-end personalization scores on the same 120 reports.
- Judge: GPT-4o-mini, temperature 0, two scores (content / presentation, 1–5).
- Generation: none (reuse confirmatory final reports).
- Cash: GPT only.

## Execution

- Script: `scripts/utility_personalization_judge.py`
- Output: `runs/confirmatory/utility_judge_gpt4omini/`
- Calls: 120; input tokens 535,967; output 14,012
- Est. GPT cash: ~$0.06–0.09

## Observed results

### v1 (initial rubric; superseded for paper claims)

| Metric | Value |
|---|---:|
| Mean content / presentation / combined | 4.508 / 4.508 / 4.508 |
| Write✓ mean vs Write✗ mean | 4.573 vs 4.250 (Δ=+0.323) |
| Pearson r | 0.183 |
| Frac identical axes | **1.000** (full collapse) |

### v2 (authoritative exploratory; forced independent evidence)

| Metric | Value |
|---|---:|
| Mean content / presentation / mean | 4.008 / 3.650 / 3.829 |
| Write✓ mean vs Write✗ mean | 3.849 vs 3.750 (Δ=+0.099) |
| Pearson r | 0.151 |
| Task-bootstrap 95% CI for Δ | [−0.021, +0.225] |
| Frac identical axes | **0.608** |

- Human spot-check template (n=20 stratified, labels pending):
  `paper/analysis/utility_human_spotcheck_20.md`

## Interpretation

- Weak, non-robust positive association under both rubrics.
- v2 reduces dimension collapse and softens ceiling but does not create a
  strong Acc↔utility link.
- Supports claim boundary: attribution = recoverability diagnostic, not
  personalization utility metric.

## Artifacts

- `runs/confirmatory/utility_judge_gpt4omini/` (v1)
- `runs/confirmatory/utility_judge_gpt4omini_v2/utility_summary.json` (**v2**)
- `paper/analysis/nobrief_and_utility_results.md`
