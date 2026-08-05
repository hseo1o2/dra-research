# Mechanism follow-up (review revision)

Date: 2026-08-05  
Summary JSON: `runs/confirmatory/analysis_mechanism_followup/mechanism_summary.json`

## Other-brief prediction breakdown (n=15)
| Pred | Count |
|---|---:|
| GT | 7 |
| Donor | 1 |
| Other | 7 |

Acc: Full 0.933 / No-brief 0.800 / Other-brief 0.467  
Figure: `brief_intervention_write_acc` (Acc bars + stacked pred)

## Robustness table rows
| Subset | n | Plan | Search | Comp | Write |
|---|---:|---:|---:|---:|---:|
| Per-GT | 120 | .808 | .550 | .592 | .800 |
| Symmetric | 120 | .733 | .542 | .608 | .708 |
| Prior-correct | 54 | .907 | .593 | .593 | .833 |
| Prior-wrong | 66 | .727 | .515 | .591 | .773 |
| Strict-quality | 90 | .822 | .567 | .611 | .811 |

## Plan→Search matrix
| | Search ✓ | Search ✗ |
|---|---:|---:|
| Plan ✓ | 65 | 32 |
| Plan ✗ | 1 | 22 |

## Token retention (actionable persona tokens)
- In brief: 0.061
- In queries: 0.019
- Brief∩persona kept in queries: 0.169
- Search✓ vs ✗ query retention: 0.020 vs 0.017

## Qualitative case
`pilot_task12_User5_seed0`: Plan✓ Search✗ Comp✗ Write✓ (User5 → User2 → User2 → User5)
