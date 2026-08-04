# Write-only mismatched-brief (other-persona brief) ablation

Date: 2026-08-05  
Status: completed  
n = 15 seed-0 reports (same 5 task groups as no-brief wave 1)

## Protocol
- Freeze Plan/Search/Compress
- Writing prompt re-injects a **donor** persona's research brief from the same task's `personas_n3` (cyclic next userid)
- Findings + user messages remain from the **GT** run
- Solar Write-stage matching; shuffle keys paired via `ablation_otherbrief_` → `pilot_`

Artifacts: `runs/ablation/otherbrief_writeonly/`  
Analysis: `analysis_paired.json`

## Paired Write Acc@1 (same 15 reports)

| Condition | Write Acc@1 |
|---|---:|
| Full pipeline (frozen) | **0.933** (14/15) |
| No-brief rewrite | **0.800** (12/15) |
| **Other-persona brief** | **0.467** (7/15) |
| Chance | 0.333 |

| Contrast | Δ | Task-bootstrap 95% CI |
|---|---:|---|
| other − full | **−0.467** | **[−0.667, −0.200]** |
| no-brief − full | −0.133 | [−0.267, 0.000] |
| other − no-brief | −0.333 | [−0.600, 0.000] |

Paired full vs other: both✓ 7, full-only✓ **7**, other-only✓ 0, both✗ 1.

Donor predicted as Write label: **1/15 (0.067)** — wrong brief hurts GT recoverability without cleanly flipping attribution to the donor.

## Interpretation
1. Injecting another persona's Planning brief **reliably harms** Writing-stage GT recoverability (CI for other−full entirely below 0).
2. Effect is **larger than no-brief**: removing the brief is mild; **replacing** it with a mismatched brief is severe.
3. Supports architectural role of brief content at Writing without claiming pure tautology of the original recovery (no-brief residual Acc still 0.80).
4. Sample is small (n=15) and seed-0 only; treat as mechanism pilot.

## Safe claim
> On a 15-report write-only pilot, substituting another persona's Planning brief reduced Writing Acc@1 from 0.933 to 0.467 (Δ=−0.467; task-bootstrap 95% CI [−0.667, −0.200]), a larger drop than brief removal alone (0.800).

## Figure
`paper/figures/brief_intervention_write_acc.{pdf,svg,png}`
