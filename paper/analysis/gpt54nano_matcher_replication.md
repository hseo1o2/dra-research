# GPT-5.4-nano matcher replication

Authoritative source directories:

- `runs/confirmatory/gpt54nano_seed0_matches/`
- `runs/confirmatory/analysis_gpt54nano_seed0_hardneg_v1/`
- `runs/confirmatory/analysis_matcher_agreement_hardneg_v1/`

The frozen seed-0 cohort contains 60 reports and 240 stage decisions.
Candidate sets and SHA-256 candidate orders match corrected Solar for all
240 paired decisions.

| Stage | Solar | GPT-5.4-nano | Agreement | Cohen's κ |
|---|---:|---:|---:|---:|
| Planning | 0.800 | 0.750 | 0.850 | 0.837 |
| Search | 0.533 | 0.467 | 0.717 | 0.680 |
| Compression | 0.567 | 0.617 | 0.700 | 0.673 |
| Writing | 0.817 | 0.850 | 0.867 | 0.855 |
| All decisions | 0.679 | 0.671 | 0.783 | 0.763 |

GPT Planning→Search is -0.283, task-cluster bootstrap 95% CI
[-0.433, -0.133]. Compression→Writing is +0.233, [0.083, 0.383].
The dip-and-recovery trajectory therefore replicates with an independent
evaluator. Agreement does not establish human validity or user utility.

Actual provider token usage and billing are unverified because the matcher
version used for this completed run did not serialize response usage. The
matcher now records input/output/total tokens and response IDs for future
calls.
