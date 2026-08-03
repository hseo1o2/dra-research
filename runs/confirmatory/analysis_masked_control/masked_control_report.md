# Identifier-Masked Control Analysis

## Technical summary

The identifier-masked condition retains the pre-specified dip-and-recovery
shape across 60 seed-0 reports: Planning accuracy is
0.750, Search is 0.600,
and Writing is 0.733. Planning→Search changes by
-15.00 percentage points
(task-cluster bootstrap 95% CI
[-26.67,
-5.00]), while Search→Writing
changes by +13.33 points
([+1.67,
+25.00]).

This supports the narrow claim that the trajectory remains after removing
surface identifier spans.

## Evidence and uncertainty

- Masked Planning→Search: -15.00
  points; task-bootstrap 95% CI
  [-26.67,
  -5.00].
- Masked Search→Writing: +13.33
  points; task-bootstrap 95% CI
  [+1.67,
  +25.00].
- The joint dip-and-recovery inequality held in
  98.44% of
  task-cluster bootstrap resamples.
- McNemar values are unclustered descriptive checks; the task-bootstrap
  intervals are the primary uncertainty summaries.

## Comparability audit

The original and masked results contain the
same 60 reports and 240 run-stage
pairs. Candidate sets, ground-truth personas, and presentation orders all
match; order agreement is
240/240
(100.0%). The paired
original-versus-masked differences are therefore identified for this
seed-0 control.

## Claim boundary

Supported: the point-estimate stage trajectory
survives identifier masking, and the paired seed-0 accuracy differences are
estimable under identical candidate presentation orders.

Not supported: that the remaining attribution signal reflects only
content-intent alignment; non-identifier shortcuts may remain.

## Next step

Replicate the masked control on seed 1 if the
submission scope requires a two-seed shortcut-effect estimate.
