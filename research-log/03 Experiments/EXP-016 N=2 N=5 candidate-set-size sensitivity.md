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
- **Artifacts**: existing seed-0 `runs/confirmatory/` artifact files (no new generation).
- **Matcher**: Solar-pro via `scripts/run_sensitivity_matching.py`.
  Tool-schema `enum` and user-prompt suffix are dynamically constructed per N.
- **Candidate order**: same SHA-256-derived deterministic shuffle as primary experiment.
- **Seed**: 0 only (120 Solar calls total: 60 for N=2 + 60 for N=5).

## Results (seed 0, n=60 per N)

| N  | Chance | Plan  | Search | Compress | Write | Δ_PS   |
|----|--------|-------|--------|----------|-------|--------|
| 2  | 0.500  | 0.817 | 0.683  | 0.600    | 0.800 | −0.134 |
| 3  | 0.333  | 0.800 | 0.533  | 0.567    | 0.817 | −0.267 |
| 5  | 0.200  | 0.750 | 0.483  | 0.517    | 0.733 | −0.267 |

All stages exceed their respective chance levels at all three candidate-set sizes.
The Planning→Search drop (Δ_PS) is −0.267 at both N=3 and N=5, −0.134 at N=2.
Writing recovery above Search: +0.117 (N=2), +0.284 (N=3), +0.250 (N=5).

## Interpretation

The dip-and-recovery trajectory is not an artefact of the three-way choice structure.
The N=2 setting (binary discrimination, chance 0.500) shows the same directional
pattern, ruling out that the low Search accuracy is driven by N=3's lower-than-chance
margin at Search. The N=5 Δ_PS matches N=3 exactly (−0.267), suggesting the
suppression effect is stable across harder discrimination tasks.

## Files

- Plan: `provenance/candidate_sensitivity_plan.json`
- Matches N=2: `runs/confirmatory/matches_sensitivity_n2/` (60 match files + summary)
- Matches N=5: `runs/confirmatory/matches_sensitivity_n5/` (60 match files + summary)
- Analysis: `paper/analysis/sensitivity_summary.json`
- Scripts: `scripts/run_sensitivity_matching.py`, `scripts/analyze_sensitivity.py`

## Cost

- Solar: 120 calls (60 × N=2, 60 × N=5), seed 0 only
- Gemini / GPT / Serper: 0
