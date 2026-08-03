# Next experiment priority after the corrected primary freeze

Date: 2026-08-03

No external model API was called while preparing this decision. Call counts
below are plans or `--estimate-only` results.

## Execution outcome

Both recommended controls were subsequently authorized and executed on
2026-08-03:

- Corrected Search views: 120 queries-only and 120 snippets-only decisions,
  with 240/240 candidate-set/order audit matches. Acc@1 is 0.600 for queries,
  0.550 for full Search, and 0.533 for snippets.
- Shuffled-actionable: 15/15 schema-valid seed-0 reports and 60/60 matched
  stage decisions. Planning and Writing favor the identity shell over the
  actionable donor; see `shuffled_actionable_control.md`.

This document is retained as the pre-execution prioritization record. The
authoritative observed results are in `search_view_control_hardneg_v1.md` and
`shuffled_actionable_control.md`.

## Current evidence boundary

The corrected two-seed primary result is already coherent across several
checks:

- Solar: 0.808 / 0.550 / 0.592 / 0.800 across
  Planning / Search / Compression / Writing.
- Planning-to-Search changes by -0.258, with a task-cluster bootstrap interval
  excluding zero; Compression-to-Writing changes by +0.208.
- Candidate-derived identity masking preserves the trajectory
  (0.725 / 0.558 / 0.575 / 0.783), while reducing Planning by 0.083.
- An independent GPT matcher reproduces the shape on seed 0 and agrees with
  Solar on 0.783 of 240 decisions (Cohen's kappa 0.763).
- Candidate-prior and task-shared-cohort checks change absolute levels but not
  the stage ordering.

The largest unresolved manuscript question is therefore not whether the
trajectory exists. It is what part of the mixed Search artifact accounts for
the sharp loss of persona recoverability.

## Ranked options

| Rank | Experiment | New generation | Matcher/API work | Expected paper value | Main risk |
|---:|---|---:|---:|---|---|
| 1 | Corrected Search component decomposition: queries-only vs snippets-only | 0 | 240 Solar calls; 5,846,315 prompt characters | Directly resolves the live mechanism question in Section 6.1 using the same 120 paired reports | Post-hoc localization, not a causal intervention |
| 2 | Shuffled-actionable donor-following control | 15 reports | generation plus 60 stage matches | Stronger evidence about whether behavior follows actionable preferences rather than the identity shell | New generation; current generation-time ablation gate already failed |
| 3 | Candidate-size sensitivity, N=2 and N=5 | 0 | 480 calls for seed 0 or 960 for both seeds | Useful robustness against the closed-set-size objection | Mostly confirms robustness; does not explain the central Search dip |
| 4 | LaMP-QA replication | 90 reports | generation plus at least 360 stage matches | Broadest external-validity gain | Highest cost, engineering surface, and scope expansion for a workshop paper |
| 5 | Continue actionable-only / identity-only to seed 1 | 30 reports | generation plus matching | Could separate demographic and actionable conditioning | Both seed-0 conditions failed the frozen completeness gate; proceeding would weaken the preregistered discipline |

## Recommendation

Run the corrected Search component decomposition next, subject to a separate
explicit API approval. It has the best information-to-cost ratio because it
reuses frozen artifacts and targets the one claim the current paper explicitly
cannot make: whether query formulation or retrieved result text drives the
Search-stage dip.

The experiment should remain paired at the report level:

1. Keep the corrected per-ground-truth candidate set and SHA-256 candidate
   order identical to the full Search match.
2. Evaluate all 120 reports with the `queries` view and all 120 with the
   `snippets` view.
3. Report Acc@1 for full Search, queries-only, and snippets-only, plus paired
   task-cluster bootstrap differences.
4. Audit 120/120 candidate sets and 240/240 candidate orders before using the
   result in the manuscript.
5. Interpret the result as cue-carrier localization only; it does not prove
   that retrieval causally removes persona information.

Estimated commands are already supported by `scripts/llm_matcher.py`; the
corrected output directories must be new so that superseded task-cohort
Search-view results cannot be resumed accidentally.

## Stop rule

If no additional API budget is approved, the current six-page paper remains a
defensible workshop submission. Keep Section 6.1's present uncertainty
language and do not cite the legacy Search-view outputs. In that case,
candidate-size and LaMP experiments remain future work rather than required
submission blockers.
