---
type: experiment
id: EXP-015
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ-Control — Does actionable content determine attribution, or does identity shell?
---

# EXP-015 Shuffled-actionable generation control

## Pre-run lock

- Objective: Determine whether persona attribution is driven by actionable preferences
  (interests, decision-making style) or by identity shell (demographics, occupation).
- Hypothesis: If actionable content drives attribution, reports generated with donor
  actionable preferences should be recovered as the donor; if identity shell dominates,
  reports should still be recovered as the shell.
- Success / failure criteria: If P(donor) > P(shell) at Planning or Writing, actionable
  content is a significant driver. If P(shell) > P(donor) significantly, identity shell
  dominates.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb` (dirty worktree)
- Model snapshot: Gemini 3.6 Flash, Solar Pro (`solar-pro`, temp=0)
- Seed / replicate IDs: seed 0
- Candidate construction: per-GT hard-negative N=3, SHA-256 order
- Population: 5 task clusters × 3 identity shells = 15 reports; cyclic donor mapping.
- Expected query/token/cost ceiling: ~4.7M generation tokens + 15×4=60 Solar calls

## Execution

- Started: 2026-08-03 ~21:00 KST (Inferred from run directory mtime 21:22)
- Completed: 2026-08-03 ~21:23 KST
- Run ID: `runs/ablation/shuffled_actionable/` + `runs/ablation/analysis_shuffled_actionable/`
- Retries / missing: 0 execution errors; 8/15 strict quality pass
- Actual token usage: generation 2,508,697; matcher (Solar) 377,697 (368,089 input, 9,608 output)
- Serper successful queries: 78 successful, 27 failed
- Actual cost: Unverified

## Observed results

**Primary (all 15 reports):**

| Stage       | Shell           | Donor          | Δ (Donor−Shell) | 95% CI              |
|-------------|-----------------|----------------|-----------------|---------------------|
| Planning    | 10/15 (0.667)   | 2/15 (0.133)   | −0.533          | [−0.933, −0.133]    |
| Search      | 7/15 (0.467)    | 5/15 (0.333)   | −0.133          | [−0.600, +0.200]    |
| Compression | 8/15 (0.533)    | 3/15 (0.200)   | −0.333          | [−0.733, 0.000]     |
| Writing     | 12/15 (0.800)   | 2/15 (0.133)   | −0.667          | [−0.933, −0.400]    |

**Strict-quality subset (8/15 reports):**

| Stage       | Shell  | Donor  |
|-------------|--------|--------|
| Planning    | 0.750  | 0.125  |
| Search      | 0.500  | 0.500  |
| Compression | 0.625  | 0.250  |
| Writing     | 0.875  | 0.125  |

SHA-256 candidate-order audit: 60/60 pass.

## Anomalies

- 7/15 reports failed strict quality gate (completeness or ledger issues). Strict-quality
  subset direction is consistent with primary result.
- Serper failed queries: 27/105 (25.7%). Above typical rate; no generation failures.

## Interpretation

Attribution is strongly anchored to identity shell at Planning and Writing (Δ = −0.533
and −0.667, both statistically reliable). Search is the only stage where shell and donor
predictions become comparably frequent (Δ = −0.133, CI includes zero), consistent with
primary Search-stage ambiguity. The intervention provides generation-time evidence that
actionable preference donor does not determine what the evaluator recovers as the persona.

## Decision / Next step

- Evidence supports §6.3 claim: persona recoverability is driven by identity shell, not
  actionable preferences.
- Seed-1 extension approved (reviewer weakness W5: n=15 too small) to increase n to 30
  and narrow CIs. Gemini generation started 2026-08-04 00:00 KST.
- Once seed-1 generation + Solar matching complete, combined n=30 results will update
  §6.3, Table tab:shuffled_actionable, and Limitations section.

## Artifacts

- Config: `runs/ablation/shuffled_actionable/` (15 report JSON files)
- Analysis: `runs/ablation/analysis_shuffled_actionable/shuffled_actionable_summary.json`
- Paper analysis: `paper/analysis/shuffled_actionable_control.md`
