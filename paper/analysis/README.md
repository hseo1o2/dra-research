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
- `nobrief_and_utility_results.md` (no-brief **n=30** + utility + equal-budget)
- `equal_budget_control.md` (seed0 equal 3500-char Solar rematch)
- `utility_human_spotcheck_20.md` / `utility_proxy_spotcheck_20.json` (independent human labels, n=20 stratified spot-check)
- `realm_review_gap_and_followup_experiments.md`
- `../../runs/ablation/nobrief_writeonly/` (30 write-only artifacts)
- `../../runs/ablation/nobrief_writeonly/analysis_paired.json` (n=30 paired)
- `../../runs/confirmatory/utility_judge_gpt4omini_v2/utility_summary.json` (utility v2)
- `../../runs/confirmatory/matches_equal_budget_3500_seed0/`
- `../../runs/confirmatory/analysis_equal_budget_3500_seed0/summary.json`
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
