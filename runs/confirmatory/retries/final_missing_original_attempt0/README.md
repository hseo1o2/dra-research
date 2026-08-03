# Seed 1 final-report retry record

Retry date: 2026-08-02

## Selection rule

Four seed 1 runs were retried because the original artifact had
`final_report not captured successfully`. Selection was based only on the
absence of the required Writing-stage artifact, not on attribution
performance or report content.

- `pilot_task24_User12_seed1`
- `pilot_task24_User13_seed1`
- `pilot_task42_User1_seed1`
- `pilot_task48_User10_seed1`

Other schema-valid runs with search/compression completeness issues were not
retried. They remain in the primary schema-valid population and are handled
through the predefined quality sensitivity analysis.

## Preservation and promotion

The four original attempt-0 artifacts and the two available attempt-0
per-run summaries are preserved in this directory. Retry attempt 1 was
written separately to:

`runs/confirmatory/retries/final_missing_attempt1/`

After local schema/completeness/ledger validation, the attempt-1 artifact and
summary for each run were promoted to the canonical
`runs/confirmatory/` directory. Retry raw search responses and its independent
global ledger remain under the attempt-1 directory.

## Artifact SHA-256

| Run | Attempt 0 | Retry attempt 1 |
|---|---|---|
| `pilot_task24_User12_seed1` | `0cb340a25adb696fede76f047b5373af82e917a6676a988071e1043d7e0a4cf1` | `c6a3b240f31eb3b657c3757d9b94b065de23d508bcd7b7270dc5dc09d9437aea` |
| `pilot_task24_User13_seed1` | `7181de42c4634ff89888af14f6c1588bf16c9ad6d7a93e489fcfc64478197ae2` | `d343f15ab5a4b1201e5e337c084093fe675f3ecf4321aff5ca2b78f7f6c3b939` |
| `pilot_task42_User1_seed1` | `a9437b1b7163c2760508dff6af306c0b7e0e3abfb8bd6c4af6554e468a480387` | `20dce6e64e7b53538cf0961b52fcca41332b744ede52e85d82fcd319a95c35f5` |
| `pilot_task48_User10_seed1` | `5d63088582e10ac220e567d0c7391284bb00321162ad68223ab0cbf22cee4393` | `d9607ccf71015be345166aca1d82a7e2fadf5a5874d2e0fe691c4aba40c2520e` |

## Retry result

- 4/4 schema-valid
- 4/4 final reports captured
- 3/4 met every success criterion
- `pilot_task42_User1_seed1` retained one ordinary completeness issue:
  no successful search source for `topic_002`
- 0 ledger issues
- 561,113 total tokens
- 28 search queries attempted; 21 successful; 7 failed

No further retry was performed for the remaining search completeness issue.
