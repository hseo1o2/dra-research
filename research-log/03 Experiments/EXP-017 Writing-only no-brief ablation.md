---
type: experiment
id: EXP-017
date: 2026-08-04
status: completed
project: DRA-personalization-attribution
rq: RQ-Mechanism — Is Writing recovery only Planning-brief re-injection?
---

# EXP-017 Writing-only no-brief ablation

## Pre-run lock

- Objective: Test whether Writing-stage persona Acc@1 collapses when the
  Planning research brief is removed from the Writing prompt.
- Hypothesis: If recovery is a pure re-injection tautology, no-brief Writing
  Acc falls toward Search-level (~0.55). If residual signal remains in findings
  / messages / synthesis, Acc stays high.
- Design: write-only regeneration; freeze Plan/Search/Compress (no Serper).
- Population: confirmatory seed-0; n=30 (10 task groups × 3 personas).
- Matcher: Solar Pro, Writing stage only; hard-neg candidate order paired via
  `ablation_nobrief_` → `pilot_` mapping.
- Cash: Gemini only (Solar ignored).

## Execution

- Wave 1: n=15 pilot
- Wave 2: n=30 with `--resume` (+15 new reports)
- Run dir: `runs/ablation/nobrief_writeonly/`
- Scripts: `scripts/write_only_nobrief.py`, `scripts/llm_matcher.py`,
  `scripts/analyze_nobrief_paired.py`
- Gemini tokens (n=30): input 752,875; output 234,589; total 987,464
- Est. Gemini cash: ~$0.25–0.80

## Observed results (paired, n=30)

| Condition | Write Acc@1 |
|---|---:|
| Full pipeline (frozen) | 0.900 (27/30) |
| No-brief rewrite | 0.833 (25/30) |
| Δ | −0.067 |
| Task-bootstrap 95% CI | [−0.167, +0.067] |

Paired counts: both✓ 24, both✗ 2, full-only✓ 3, nobrief-only✓ 1.

Plan✓Search✗ subset (n=8): full Write✓ 7/8, no-brief Write✓ 6/8.

Wave split: wave1 Δ=−0.133; wave2 Δ=0.000; pool prefers n=30.

## Interpretation

- Re-injection may help some cases, but Writing Acc remains high without the
  brief → **not a pure architectural tautology**.
- Δ CI includes 0 → do not claim a statistically significant collapse.
- Safe claim: substantial residual Writing recoverability without brief
  re-injection on this seed-0 slice.

## Artifacts

- `runs/ablation/nobrief_writeonly/analysis_paired.json`
- `paper/analysis/nobrief_and_utility_results.md`
