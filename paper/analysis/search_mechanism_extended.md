# Extended Search mechanism analyses (corrected)

Date: 2026-08-05  
Authoritative summary: `runs/confirmatory/analysis_search_mechanism_extended/search_mechanism_corrected_summary.json`

## Query definition (critical fix)

- `queries_requested` mean **29.4** (planner proposals; many rejected)
- `queries_attempted` mean **6.9** (report cap = 7)
- `status=ok` mean **5.2** ← used for Search artifact + retention probes

Paper Generation Stack text updated accordingly. Do **not** cite 31.4 as executed queries.

## Embedding alignment (ok queries)

| Metric | Mean | Note |
|---|---:|---|
| persona–brief | 0.269 | |
| persona–query | 0.212 | |
| brief–query | 0.493 | topic preserved |
| brief−query drop | 0.057 | CI [0.042, 0.075] |
| Search✓ − ✗ persona–query | 0.055 | CI [0.019, 0.088] |

## Feature retention (ok queries)

| Bucket | Brief | Query |
|---|---:|---:|
| Identity | 0.100 | 0.020 |
| Interests | 0.081 | 0.010 |
| Goals/constraints | 0.075 | 0.008 |
| Decision style | 0.020 | 0.002 |

## Lexical actionable

0.068 (brief) → 0.008 (ok queries)

## Dropped from main text (submission polish)

- Matcher certainty proxy
- Surface generic-phrase rate + false “31.4 queries” expansiveness claim
- Second qualitative case (appendix only)
