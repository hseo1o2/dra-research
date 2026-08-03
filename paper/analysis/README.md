# Analysis artifact status

## Authoritative corrected primary

- `contribution_insights_hardneg_v1.json`
- `contribution_insights_hardneg_v1.md`
- `../../runs/confirmatory/analysis_candidate_prior/`
- `../../runs/confirmatory/analysis_masked_identity_hardneg_v1/`
- `../../runs/confirmatory/masked_identity_hardneg_v1/matches/`
- `../../runs/confirmatory/matches_hardneg_v1/`
- `../../runs/confirmatory/analysis_hardneg_v1/`
- `../figures/stage_attribution_trajectory.{pdf,svg,png}`
- `next_experiment_priority.md`
- `search_view_control_hardneg_v1.md`
- `../../runs/confirmatory/analysis_search_views_hardneg_v1/`
- `shuffled_actionable_control.md`
- `../../runs/ablation/analysis_shuffled_actionable/`
- `../PDF_QA.md`

These artifacts use the frozen per-ground-truth
`attribution_candidate_set_n3` protocol. The candidate audit passes 120/120
reports.

## Superseded development artifacts

The following files use the earlier task-level `personas_n3` candidate cohort
and must not be cited as hard-negative results:

- `contribution_insights.{json,md,html,ipynb}`
- `identifier_masked_control.md`
- `identifier_masked_control_summary.json`

They are retained only to preserve the protocol history. A stronger
candidate-derived identity-masking control has now been executed under the
corrected protocol; the older NER-only files remain superseded. Corrected
Search-view Solar matching has now been executed for all 120 paired reports;
the authoritative result is `search_view_control_hardneg_v1.md`.
