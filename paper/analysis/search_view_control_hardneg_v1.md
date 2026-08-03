# Corrected Search component control

Date: 2026-08-03

This is the authoritative Search-view analysis under the frozen per-ground-
truth hard-negative protocol. The earlier task-cohort Search-view outputs are
superseded and must not be cited.

## Protocol

- Reports: 120 (20 task clusters, two generation seeds)
- Full Search, queries-only, and snippets-only use the same report population.
- Queries/full/snippets candidate-set and SHA-256 order audit: 240/240 pass.
- Matcher: Solar Pro
- Views are post-hoc decompositions of the same Search artifacts.
- Queries-only usage: 616,690 tokens (597,260 input; 19,430 output).
- Snippets-only usage: 725,463 tokens (706,258 input; 19,205 output).

## Results

| View | Acc@1 |
|---|---:|
| Full Search | 0.550 |
| Queries only | 0.600 |
| Snippets only | 0.533 |

Paired task-cluster bootstrap differences:

| Contrast | Difference | 95% CI |
|---|---:|---:|
| Queries - full | +0.050 | [0.000, 0.108] |
| Snippets - full | -0.017 | [-0.067, 0.033] |
| Queries - snippets | +0.067 | [-0.008, 0.142] |

The queries-only point estimate is highest and its advantage over full Search
is consistent across both seeds (+0.050 in each). However, the direct
queries-versus-snippets interval includes zero. The defensible conclusion is
therefore directional: mixing retrieved snippets with generated queries does
not restore persona recoverability and may dilute a modest query-carried
signal, but the present sample does not establish that one component uniquely
causes the Search-stage dip.

## Claim boundary

This control localizes observable attribution cues in post-hoc artifact views.
It is not a generation-time intervention and does not establish that
retrieval causally removes persona information or reduces report utility.

Machine-readable source:
`runs/confirmatory/analysis_search_views_hardneg_v1/search_view_summary.json`.
