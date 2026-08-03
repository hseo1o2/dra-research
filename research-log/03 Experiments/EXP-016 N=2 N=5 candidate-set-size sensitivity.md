---
type: experiment
status: completed
date: 2026-08-03
related_decisions: [DEC-007]
related_experiments: [EXP-012]
---

# EXP-016 Candidate-Set-Size Sensitivity (N=2/N=5)

## Hypothesis

If the dip-and-recovery trajectory is a genuine artifact-signal effect rather than
an artefact of the three-way (N=3) choice structure, the same trajectory shape
should appear at N=2 (harder to fool by chance) and N=5 (harder overall).

## Protocol

- **Candidate plan**: `provenance/candidate_sensitivity_plan.json` — 60 experiments
  × N∈{2,3,5}, built from same-domain actionable-token Jaccard ranking.
  N=3 re-computation matches manifest 60/60 exactly (validation gate passed).
- **Artifacts**: existing `runs/confirmatory/` artifact files, seeds 0 and 1.
- **Matcher**: Solar-pro via `scripts/run_sensitivity_matching.py`.
  Tool-schema `enum` and user-prompt suffix are dynamically constructed per N.
- **Candidate order**: same SHA-256-derived deterministic shuffle as primary experiment.
- **Seeds**: 0 and 1 (240 Solar calls total: 60×2 for N=2 + 60×2 for N=5).

## Results (seeds 0 and 1, n=120 per N)

| N  | Chance | Plan  | Search | Compress | Write | Δ_PS   |
|----|--------|-------|--------|----------|-------|--------|
| 2  | 0.500  | 0.842 | 0.633  | 0.625    | 0.775 | −0.209 |
| 3  | 0.333  | 0.808 | 0.550  | 0.592    | 0.800 | −0.258 |
| 5  | 0.200  | 0.758 | 0.471  | 0.525    | 0.717 | −0.287 |

All stages exceed their respective chance levels at all three candidate-set sizes.
The Planning→Search drop (Δ_PS) grows monotonically with N: −0.209 (N=2), −0.258 (N=3), −0.287 (N=5).
Writing recovery above Search: +0.142 (N=2), +0.250 (N=3), +0.246 (N=5).

## Interpretation

The dip-and-recovery trajectory is not an artefact of the three-way choice structure.
The N=2 setting (binary discrimination, chance 0.500) shows the same directional
pattern, ruling out that the low Search accuracy is driven by N=3's lower-than-chance
margin at Search. The Δ_PS grows monotonically with N, suggesting the suppression
effect becomes more pronounced as discrimination becomes harder.

## Files

- Plan: `provenance/candidate_sensitivity_plan.json`
- Matches N=2: `runs/confirmatory/matches_sensitivity_n2/` (60 match files + summary)
- Matches N=5: `runs/confirmatory/matches_sensitivity_n5/` (60 match files + summary)
- Analysis: `paper/analysis/sensitivity_summary.json`
- Scripts: `scripts/run_sensitivity_matching.py`, `scripts/analyze_sensitivity.py`

## Cost

- Solar: 240 calls (60×2 × N=2, 60×2 × N=5), seeds 0 and 1
- Gemini / GPT / Serper: 0
