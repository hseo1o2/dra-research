---
type: experiment
id: EXP-020
date: 2026-08-05
status: completed
project: DRA-personalization-attribution
rq: RQ-Mechanism — Does mismatched Planning brief content change Writing recoverability?
---

# EXP-020 Mismatched-brief write-only ablation

## Design
- n=15 seed0 (tasks 2,4,7,9,12)
- Write-only; donor brief = cyclic next persona in `personas_n3`
- Solar Write match

## Results (paired)
| Condition | Write Acc |
|---|---:|
| Full | 0.933 |
| No-brief | 0.800 |
| Other-brief | **0.467** |
| Δ (other−full) | −0.467 CI [−0.667, −0.200] |

Donor pred rate: 0.067

## Artifacts
`runs/ablation/otherbrief_writeonly/`, `paper/analysis/otherbrief_writeonly.md`
