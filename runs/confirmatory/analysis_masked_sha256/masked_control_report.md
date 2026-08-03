# Identifier-Masked Control Analysis

## Technical summary

The identifier-masked condition retains the pre-specified dip-and-recovery
shape across 120 two-seed reports: Planning accuracy is
0.725, Search is 0.550,
and Writing is 0.725. Planning→Search changes by
-17.50 percentage points
(task-cluster bootstrap 95% CI
[-28.33,
-7.50]), while Search→Writing
changes by +17.50 points
([+5.83,
+29.17]).

This supports the narrow claim that the trajectory remains after removing
surface identifier spans.

## Evidence and uncertainty

- Masked Planning→Search: -17.50
  points; task-bootstrap 95% CI
  [-27.50,
  -7.50].
- Masked Search→Writing: +17.50
  points; task-bootstrap 95% CI
  [+6.67,
  +28.33].
- The joint dip-and-recovery inequality held in
  99.72% of
  task-cluster bootstrap resamples.
- McNemar values are unclustered descriptive checks; the task-bootstrap
  intervals are the primary uncertainty summaries.

## Comparability audit

The original and masked results contain the
same 120 reports and 480 run-stage
pairs. Candidate sets, ground-truth personas, and presentation orders all
match; order agreement is
480/480
(100.0%). The paired
original-versus-masked differences are therefore identified for this
two-seed control.

## Claim boundary

Supported: the point-estimate stage trajectory
survives identifier masking, and the paired two-seed accuracy differences are
estimable under identical candidate presentation orders.

Not supported: that the remaining attribution signal reflects only
content-intent alignment; non-identifier shortcuts may remain.

## Next step

Replicate with a second matcher or dataset if the
submission scope requires broader shortcut robustness.
