# Corrected primary contribution synthesis

This is the manuscript-facing synthesis for the frozen per-GT hard-negative
protocol. Candidate audit: 120/120 reports pass.

## Primary trajectory

| Stage | Solar Acc@1 | Task-cluster bootstrap 95% CI |
|---|---:|---:|
| Planning | 0.808 | [0.683, 0.917] |
| Search | 0.550 | [0.433, 0.658] |
| Compression | 0.592 | [0.483, 0.692] |
| Writing | 0.800 | [0.708, 0.883] |

Macro Acc@1 is 0.688 against three-way chance 0.333.

## Report-level transitions

| Transition | Correct→wrong | Wrong→correct | Net |
|---|---:|---:|---:|
| Planning→Search | 32 | 1 | -31 |
| Search→Compression | 8 | 13 | +5 |
| Compression→Writing | 6 | 31 | +25 |

Planning→Search changes by -0.258, 95% CI [-0.333, -0.175].
Search→Compression changes by +0.042, [-0.025, 0.108], so this intermediate
increase is unresolved. Compression→Writing changes by +0.208,
[0.142, 0.283].

Among 32 reports that are correct at Planning and wrong at Search, 24 (75.0%)
are correct again at Writing. Among all 54 Search errors, 33 (61.1%) are
correct at Writing.

## Solar versus BM25

| Stage | Solar−BM25 | Task-cluster bootstrap 95% CI |
|---|---:|---:|
| Planning | +0.175 | [0.083, 0.258] |
| Search | -0.017 | [-0.125, 0.092] |
| Compression | +0.025 | [-0.058, 0.117] |
| Writing | +0.225 | [0.142, 0.308] |

Solar's advantage is supported at Planning and Writing, but not at Search or
Compression. The defensible contribution is stage-dependent evaluator
advantage, not universal LLM-matcher superiority.

## Quality and seed sensitivity

- Success-criteria subset (n=90): 0.822/0.567/0.611/0.811.
- No-completeness-error subset (n=91): 0.824/0.571/0.615/0.813.
- Largest seed-1-minus-seed-0 point difference is +0.050 at Compression; all
  seed-difference intervals include zero.
- 55/120 reports are correct at every stage; 11/120 are wrong at every stage.

## Candidate construction and identity masking

- An artifact-free candidate-centrality heuristic identifies 27/60
  per-GT construction centers: 0.450, task-cluster bootstrap 95% CI
  [0.333, 0.567].
- A symmetric task-shared candidate cohort retains the trajectory:
  0.733/0.542/0.608/0.708.
- Candidate-derived identity masking uses all three candidate profiles and
  preserves candidate sets/orders for 480/480 paired decisions.
- Masked Acc@1 is 0.725/0.558/0.575/0.783.
- Masked-minus-full is -0.083 at Planning, 95% CI [-0.150, -0.025].
  Search (+0.008), Compression (-0.017), and Writing (-0.017) intervals
  include zero.
- Within the masked condition, Planning→Search is -0.167
  [-0.258, -0.067] and Compression→Writing is +0.208 [0.100, 0.308].

The absolute hard-negative accuracy can contain a candidate-construction
prior, and direct identity evidence explains part of Planning accuracy.
Neither issue explains the stage ordering or late Writing recovery.

## Claim boundary

Acc@1 measures persona recoverability, not utility, factual quality, user
satisfaction, or causal stage influence. Conservative masking can remove
task-relevant content through NER false positives while leaving paraphrased
identity cues. Cross-matcher and cross-dataset replication remain pending.

Machine-readable source:
`paper/analysis/contribution_insights_hardneg_v1.json`.
