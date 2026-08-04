---
type: experiment
id: EXP-019
date: 2026-08-05
status: completed
project: DRA-personalization-attribution
rq: RQ-Control — Is the Search dip a matcher character-budget artifact?
---

# EXP-019 Equal character-budget rematch

## Pre-run lock

- Objective: Re-match seed-0 confirmatory artifacts with a uniform char budget
  across all stages and test whether dip-and-recovery survives.
- Budget: 3,500 characters per stage (matches default Search cap).
- Population: 60 seed-0 reports × 4 stages = 240 Solar calls.
- Cash: 0 (Solar credit ignored).

## Execution

- CLI: `scripts/llm_matcher.py --batch-dir runs/confirmatory --seed 0
  --equal-char-budget 3500 --output-dir runs/confirmatory/matches_equal_budget_3500_seed0`
- Analysis: `scripts/analyze_equal_budget.py`
- Completed: 2026-08-05

## Results (paired vs default seed0)

| Stage | Default | Equal | Δ | 95% CI |
|---|---:|---:|---:|---|
| Plan | 0.800 | 0.800 | 0.000 | [0, 0] |
| Search | 0.533 | 0.517 | −0.017 | [−0.05, 0] |
| Compress | 0.567 | 0.600 | +0.033 | [−0.033, 0.100] |
| Write | 0.817 | 0.800 | −0.017 | [−0.067, 0.033] |

Dip preserved: Search < Plan, Write > Search.

## Interpretation

Character-budget confound is not a sufficient explanation of the Search dip
under this protocol.
