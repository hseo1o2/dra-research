# Candidate Protocol Blocker — 2026-08-03

## Finding

The frozen manifest defines a separate three-way attribution set for every
ground-truth persona:

`[GT, top-1 same-domain actionable-Jaccard negative, top-2 negative]`.

The original matcher lookup instead returned the three personas sampled for
the task (`personas_n3`). An audit of the 120 full-report match files found:

- match files audited: 120
- exact candidate-set matches with the frozen per-GT protocol: 6
- mismatches: 114
- affected stage decisions: all decisions belonging to those 114 reports

The generated DRA artifacts are unaffected. The affected outputs are matcher
results and anything derived from them: primary accuracy, masked and
search-view controls, non-LLM baselines, tables, figures, and paper claims.

## Resolution implemented without API calls

- Shared candidate lookup now reads
  `experiment.attribution_candidate_set_n3` for full,
  actionable-only, and identity-only conditions.
- Shuffled-actionable intentionally retains the task cohort because both the
  identity shell and cyclic actionable donor must be available to the matcher.
- Existing results remain untouched as a record of the task-cohort protocol.
- Corrected Solar results must be written to
  `runs/confirmatory/matches_hardneg_v1/`.
- `provenance/candidate_sensitivity_plan.json` freezes N=2, N=3, and N=5 as
  deterministic prefixes of the same ranking. Recomputed N=3 matches the
  manifest for all 60 confirmatory experiments.

## Resolution status

Corrected full Solar matching is complete in
`runs/confirmatory/matches_hardneg_v1/`: 120 reports, 480 stage decisions,
and 120/120 exact candidate-set audit matches. Corrected non-LLM baselines
also pass 360/360 file-level audits. Primary statistics and figures have been
regenerated, so the full-condition values in `paper/main.tex` are no longer
provisional.

A stronger candidate-derived identity-masking control has now been rerun
under the corrected candidate protocol: 120 reports, 480 stage decisions,
120/120 candidate audit pass, and 480/480 full-versus-masked order matches.
The older NER-only values remain superseded. Search-view Solar outputs have
not been rerun and remain excluded from current paper claims.

## Required reruns

1. Solar full, seeds 0 and 1: **completed, 480 stage calls**.
2. Random/BM25/Embedding baselines: **completed offline for both seeds** in
   `baselines_hardneg_v1_seed0/` and `baselines_hardneg_v1_seed1/`.
3. Candidate-derived identity-masked Solar, seeds 0 and 1:
   **completed, 480 stage calls**.
4. Search query-only and snippet-only Solar if retained in the paper.
5. Full-condition summaries, bootstrap analyses, tables, and figures:
   **completed**. Control-dependent outputs remain pending.
6. GPT replication and N sensitivity, if run, must use the corrected frozen
   candidate sets.

The complete retained-control Solar estimate is 1,200 calls and 32,166,667
prompt characters: full 480, identifier-masked 480, and two Search views 240.
Of these, full 480 and candidate-derived identity-masked 480 calls have been
executed; the remaining 240 Search-view calls are estimates only.
