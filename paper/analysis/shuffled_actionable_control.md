# Shuffled-actionable intervention

Date: 2026-08-03

## Protocol and quality

- Frozen subset: 5 task clusters × 3 identity shells = 15 reports, seed 0.
- Each report combines one candidate's identity shell with the next
  candidate's actionable preferences under the frozen cyclic donor mapping.
- Generation: 15/15 schema-valid, 8/15 strict success, execution errors 0.
- Generation usage: 2,508,697 tokens; 78 successful and 27 failed searches.
- Matching: Solar Pro, 15 reports × 4 stages = 60 decisions; 377,697 tokens
  (368,089 input; 9,608 output).
- SHA-256 candidate-order audit: 60/60 pass.

## Primary result

| Stage | Shell | Actionable donor | Other | Donor - shell | Task-bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| Planning | 10/15 (0.667) | 2/15 (0.133) | 3/15 | -0.533 | [-0.933, -0.133] |
| Search | 7/15 (0.467) | 5/15 (0.333) | 3/15 | -0.133 | [-0.600, 0.200] |
| Compression | 8/15 (0.533) | 3/15 (0.200) | 4/15 | -0.333 | [-0.733, 0.000] |
| Writing | 12/15 (0.800) | 2/15 (0.133) | 1/15 | -0.667 | [-0.933, -0.400] |

The intervention does not make reports follow the actionable donor. Persona
recoverability remains strongly anchored to the identity shell at Planning
and Writing. Search is the only stage where donor and shell predictions become
comparably frequent, consistent with the primary Search-stage ambiguity.

## Strict-quality sensitivity

Among the eight reports meeting all success criteria, shell versus donor
rates are 0.750/0.125 at Planning, 0.500/0.500 at Search, 0.625/0.250 at
Compression, and 0.875/0.125 at Writing. The small subset is imprecise, but
the Planning and Writing direction is unchanged.

## Claim boundary

This is generation-time intervention evidence about which candidate identity
is recoverable from artifacts. It does not prove that actionable preferences
have no effect, identify latent user utility, or show that demographic
conditioning causally improves the report. The control uses one generation
seed and only 15 reports.

Machine-readable source:
`runs/ablation/analysis_shuffled_actionable/shuffled_actionable_summary.json`.
