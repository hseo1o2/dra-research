# Identifier-Masked Control Analysis

> **SUPERSEDED PROTOCOL ARTIFACT.** These matcher values use task-level
> `personas_n3`. A corrected per-GT masked matcher rerun has not been
> executed, so this file must not support manuscript claims.

## Technical summary

The corrected identifier-masked condition retains the pre-specified
dip-and-recovery shape across 120 reports from two generation seeds:
Planning accuracy is 0.725, Search is 0.550, Compression is 0.608, and
Writing is 0.725.

Planning→Search changes by -17.50 percentage points (task-cluster bootstrap
95% CI [-28.33, -7.50]), while Search→Writing changes by +17.50 points
([+5.83, +29.17]). The joint inequality held in 99.72% of 5,000
task-cluster bootstrap resamples.

## Paired condition effects

| Stage | Masked−original | Task-bootstrap 95% CI |
|---|---:|---:|
| Planning | -0.008 | [-0.033, 0.017] |
| Search | +0.008 | [-0.042, 0.067] |
| Compression | 0.000 | [-0.042, 0.042] |
| Writing | +0.017 | [-0.017, 0.050] |

All intervals include zero. The corrected result therefore provides no
evidence that masking common named-entity spans materially reduces
attribution accuracy.

## Comparability audit

The original and masked results contain the same 120 reports and 480
run-stage pairs. Candidate sets, ground-truth personas, and SHA-256 candidate
presentation orders match for all 480 pairs.

The corrected masker handles the v2 `search_trace.sources` field, including
source titles and snippets. This result supersedes the earlier seed-0 control,
whose Search source fields were not masked because the implementation only
handled the legacy `results` key.

## Claim boundary

Supported: the stage trajectory survives corrected two-seed identifier
masking, and paired effects are estimable under identical candidate orders.

Not supported: that the remaining attribution signal reflects only
content-intent alignment; identifiers missed by NER and other lexical
shortcuts may remain.

## Reproduction

```bash
python scripts/analyze_masked_control.py \
  --original-dir runs/confirmatory/matches_sha256 \
  --masked-dir runs/confirmatory/masked_sha256/matches \
  --output-dir runs/confirmatory/analysis_masked_sha256
```
