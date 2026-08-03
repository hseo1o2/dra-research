# Contribution synthesis from completed experiments

> **SUPERSEDED PROTOCOL ARTIFACT.** The values below use task-level
> `personas_n3`, not the frozen per-GT hard-negative candidate protocol.
> Do not cite them. Use `contribution_insights_hardneg_v1.md` and
> `contribution_insights_hardneg_v1.json`.

## Recommended paper thesis

Stage-wise persona attribution should be presented as a **recoverability-flow
diagnostic** for multi-stage research agents. Its value is not only that it
assigns one accuracy to each stage; it identifies which individual reports
lose and later regain recoverable persona evidence as the pipeline transforms
the request.

## Contribution 1 — A transition-aware diagnostic

The aggregate trajectory is Planning 0.733, Search 0.542, Compression 0.608,
and Writing 0.708 over 120 reports. The stronger result comes from pairing the
same reports across stages:

| Transition | Correct→wrong | Wrong→correct | Net |
|---|---:|---:|---:|
| Planning→Search | 27 | 4 | -23 |
| Search→Compression | 9 | 17 | +8 |
| Compression→Writing | 6 | 18 | +12 |

Among the 27 reports that lose attribution from Planning to Search, 21
(77.8%) are attributable again at Writing. Among all 55 Search errors, 29
(52.7%) are correct at Writing. This supports a report-level
**loss-and-recovery** claim, not merely a visual dip in four aggregate means.

## Contribution 2 — The Search bottleneck has two components

Post-hoc Search views separate query formulation from retrieved title/snippet
content while holding reports, candidates, candidate order, and matcher fixed:

| Search view | Seed 0 | Seed 1 | Combined |
|---|---:|---:|---:|
| Query + snippet | 0.567 | 0.517 | 0.542 |
| Query-only | 0.633 | 0.583 | 0.608 |
| Snippet-only | 0.567 | 0.483 | 0.525 |

Query-only exceeds the full view by +0.067 with task-cluster bootstrap 95% CI
[0.017, 0.117]. Snippet-only differs from full by -0.017
[-0.100, 0.083]. The query-only gain is +0.067 in each seed, and coverage is
not a plausible main explanation: the full capped artifact exposes 626/629
successful query strings and all queries in 117/120 reports.

The refined interpretation is that query formulation accounts for part of
the Planning→Search loss, while mixing persona-conditioned queries with
retrieved-result snippets creates additional dilution for the attribution
matcher. Because these are post-hoc views, they do not establish that snippets
causally harm generation.

## Contribution 3 — Recoverable evidence changes across stages

Across the paired reports from both seeds, Solar's advantage over BM25 is:

| Stage | Solar−BM25 | Task-bootstrap 95% CI |
|---|---:|---:|
| Planning | +0.150 | [0.075, 0.225] |
| Search | +0.100 | [0.008, 0.192] |
| Compression | +0.108 | [0.025, 0.192] |
| Writing | +0.217 | [0.100, 0.333] |

The Solar–BM25 gap is smallest at Search and largest at Writing in each
individual seed, although the gap magnitudes vary (Search: 0.050/0.150;
Writing: 0.300/0.133 for seeds 0/1). The defensible interpretation is that
Search exposes less additional evidence usable by a contextual matcher beyond
direct lexical overlap, whereas Writing contains more contextual or
distributed evidence. This is evidence about the **type of recoverable cue**,
not proof of an internal causal mechanism.

## Contribution 4 — The trajectory is not explained by obvious artifact defects

- Corrected two-seed identifier masking changes accuracy by -0.008, +0.008,
  0.000, and +0.017 across the four stages. All task-bootstrap intervals
  include zero. The masked trajectory is 0.725/0.550/0.608/0.725.
- Restricting to the 90 reports satisfying every success criterion produces
  0.767/0.567/0.644/0.756.
- Excluding completeness errors produces 0.769/0.571/0.648/0.758 on 91
  reports.

Both quality-filtered populations retain the same stage ordering. Named
entities and recorded completeness defects therefore do not explain away the
loss-and-recovery shape, although other shortcuts may remain.

## Contribution 5 — Shape stability and endpoint fragility coexist

Both generation seeds show Planning→Search loss followed by recovery, but
Writing differs by -0.117 for seed 1 relative to seed 0, with paired
task-bootstrap 95% CI [-0.233, -0.033]. Planning has identical aggregate
accuracy across seeds, while Search and Compression differ only modestly.

The correct claim is therefore:

> The loss-and-recovery shape replicates across two seeds, while the magnitude
> of final-stage recoverability remains generation-sensitive.

Do not claim seed-invariant endpoint accuracy.

## Recommended contribution framing

1. **Methodological:** an N-way, stage-wise, transition-aware diagnostic with
   deterministic candidate ordering and trace-level evaluation.
2. **Empirical:** a report-level loss-and-recovery phenomenon centered on the
   Search transformation.
3. **Localization:** query-only/snippet-only views that separate partial
   query-formulation loss from dilution in the retrieved-result mixture.
4. **Comparative:** a stage-dependent Solar–BM25 gap consistent with a shift
   from sparse lexical to contextual/distributed evidence.
5. **Robustness:** persistence under identifier masking and pre-specified
   quality filters, paired with an explicit finding of Writing-stage seed
   sensitivity.

## Claim boundary

Acc@1 measures persona recoverability. It does not establish personalization
utility, user satisfaction, factual quality, or causal influence of a stage.
Baseline and identifier-masking comparisons cover both seeds. Cross-model or
cross-dataset replication has not yet been executed.

## Reproduction

```bash
python scripts/analyze_contribution_insights.py
jupyter nbconvert --execute --to notebook --inplace \
  paper/analysis/contribution_insights.ipynb
```

Machine-readable output:
`paper/analysis/contribution_insights.json`.
