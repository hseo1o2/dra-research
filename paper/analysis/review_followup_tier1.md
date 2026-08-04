# Review follow-up analyses (Tier 1)

Date: 2026-08-05  
Status: completed (network-free re-analysis of frozen matches)  
Script: `scripts/analyze_review_followup.py`  
Artifact: `runs/confirmatory/analysis_review_followup/review_followup_summary.json`

## Construct definition (locked)

> **Persona signal / persona recoverability** means only information in a stage
> artifact that supports closed-set recovery of the conditioning persona among
> hard-negative candidates. It does **not** imply causal mediation,
> personalization utility, or factual quality.

## Primary / secondary / exploratory

| Tier | Contrasts |
|---|---|
| **Primary** | Plan→Search Δ; Compress→Write Δ; Plan✓Search✗ Write recovery rate |
| **Secondary** | Masking, matcher replication, equal-budget, **symmetric task-shared** |
| **Exploratory** | Domain, User10 attractor, utility, Search views |

---

## 1. Symmetric (task-shared) vs per-GT hard-neg

| Protocol | Plan | Search | Compress | Write | Δ P→S [CI] | Δ C→W [CI] | Dip? |
|---|---:|---:|---:|---:|---|---|:---:|
| Per-GT hard-neg (primary) | 0.808 | 0.550 | 0.592 | 0.800 | −0.258 [−0.321, −0.194] | +0.208 [+0.153, +0.264] | ✓ |
| Symmetric task-shared | 0.733 | 0.542 | 0.608 | 0.708 | −0.192 [−0.250, −0.128] | +0.100 [+0.028, +0.167] | ✓ |

### Plan✓ Search✗ recovery

| Protocol | n loss | Write recover | Rate [CI] |
|---|---:|---:|---|
| Hard-neg | 32 | 24 | 0.750 [0.546, 0.914] |
| Symmetric | 27 | 21 | 0.778 [0.600, 0.926] |

**Interpretation:** Absolute Acc falls under symmetric candidates (prior
deflation), but **trajectory shape and recovery rate remain**. Primary
scientific claim should emphasise paired transitions, not absolute Acc@1.

---

## 2. Candidate-only prior–adjusted subset

Artifact-free centrality prior Acc = **0.450** (27/60 sets; chance 0.333;
CI [0.333, 0.567]).

| Subset | n | Plan | Search | Compress | Write | Δ P→S | Dip? |
|---|---:|---:|---:|---:|---:|---:|:---:|
| All hard-neg | 120 | 0.808 | 0.550 | 0.592 | 0.800 | −0.258 | ✓ |
| Prior **wrong** only | 66 | 0.727 | 0.515 | 0.591 | 0.773 | −0.212 [−0.325, −0.105] | ✓ |
| Prior correct only | 54 | (see JSON) | | | | | |

**Interpretation:** Even after removing reports whose GT is already implied by
candidate structure, dip-and-recovery holds. Candidate prior inflates absolute
levels; it does not create the within-report stage ordering.

---

## 3. Chance-normalized Acc (N = 2 / 3 / 5)

\[
\mathrm{Acc}_{norm} = \frac{\mathrm{Acc}-1/N}{1-1/N}
\]

| N | Plan_norm | Search_norm | Comp_norm | Write_norm | Dip raw? |
|---:|---:|---:|---:|---:|:---:|
| 2 | 0.683 | 0.267 | 0.250 | 0.550 | ✓ |
| 3 | 0.712 | 0.325 | 0.388 | 0.700 | ✓ |
| 5 | 0.698 | 0.338 | 0.406 | 0.646 | ✓ |

**Interpretation:** Planning recoverability is nearly flat across N after
chance normalization (~0.68–0.71). Raw Acc drop with larger N is expected
discrimination difficulty, not collapse of the phenomenon.

---

## 4. User10 exposure-normalized false rate

Definition: \(P(\hat p=\mathrm{User10} \mid \mathrm{User10}\in C,\ \mathrm{GT}\neq\mathrm{User10})\).

| Stage | Exposure n | False→U10 | Rate | Chance |
|---|---:|---:|---:|---:|
| Plan | 58 | 8 | **0.138** | 0.333 |
| Search | 58 | 23 | **0.397** | 0.333 |
| Compress | 58 | 19 | **0.328** | 0.333 |
| Write | 58 | 13 | **0.224** | 0.333 |

**Interpretation:** After exposure normalization, User10 is **not** a strong
attractor at Plan/Write (below chance). At Search the rate is only mildly
above chance (0.40 vs 0.33); raw confusion counts overstate the attractor
story because of high exposure.

---

## Claim language (safe)

1. Primary contribution is **report-level recoverability localization**, not high absolute Acc@1.
2. Symmetric and prior-wrong subsets preserve dip-and-recovery → shape is not a candidate-construction artifact alone.
3. Chance-normalized Planning is stable across N.
4. User10 “attractor” is mostly Search-stage mild elevation after exposure control.

---

## Figures (generated 2026-08-05)

Script: `scripts/plot_review_followup_figures.py`  
Regenerate: `open_deep_research/.venv/bin/python scripts/plot_review_followup_figures.py`

| Figure file | Content | In `main.tex` |
|---|---|---|
| `protocol_trajectory_comparison.*` | Hard-neg / symmetric / prior-wrong trajectories + CI | `fig:protocol_trajectories` |
| `report_level_transitions.*` | Lost vs gained bars, both protocols | `fig:report_transitions` |
| `recovery_flow_plan_search_write.*` | 32 → 24/8 recovery flow | `fig:recovery_flow` |
| `chance_normalized_n_sensitivity.*` | Chance-norm Acc for N=2/3/5 | `fig:chance_norm_n` |
| `user10_exposure_false_rate.*` | Exposure-normalized U10 false rate | `fig:user10_exposure` |
| `nobrief_write_paired.*` | Full vs no-brief Write Acc (n=30) | `fig:nobrief_paired` |
