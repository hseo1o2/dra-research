# Writing No-Brief Ablation & Attribution–Utility Correlation

Date: 2026-08-04  
Status: executed (Package B core; no-brief expanded to **n=30**)  
Cash models: Gemini (write-only) + GPT-4o-mini (utility); Solar matcher free

## Goals

1. Test whether Writing-stage persona recoverability depends on Planning brief re-injection.
2. Test whether Writing Acc@1 correlates with personalization utility scores.

---

## Experiment A — Writing-only no-brief ablation

### Protocol
- **n = 30** confirmatory seed-0 reports (10 task groups × 3 personas)
  - Wave 1: n=15 pilot → Wave 2: +15 expansion (same protocol, `--resume`)
- Frozen Plan/Search/Compress reused (no Serper)
- Writing regenerated with Gemini 3.6 Flash using findings + user messages **without** `<Research Brief>`
- Solar Pro matcher on Writing stage only; candidate sets/orders paired to pilot runs via `ablation_nobrief_` → `pilot_` mapping
- Artifacts: `runs/ablation/nobrief_writeonly/`
- Paired analysis: `runs/ablation/nobrief_writeonly/analysis_paired.json`
- Analyzer: `scripts/analyze_nobrief_paired.py`

### Scripts
- `scripts/write_only_nobrief.py --n 30 --execute --resume`
- `scripts/llm_matcher.py --batch-dir runs/ablation/nobrief_writeonly --stage write --resume`
- `scripts/analyze_nobrief_paired.py`

### Primary paired result (n=30, authoritative)

| Condition | Write Acc@1 |
|---|---:|
| Full pipeline Writing (frozen) | **0.900** (27/30) |
| No-brief write-only rewrite | **0.833** (25/30) |
| Δ (nobrief − full) | **−0.067** |
| Task-cluster bootstrap 95% CI | **[−0.167, 0.067]** |

### Paired transition counts (n=30)
| Pattern | Count |
|---|---:|
| Both correct | 24 |
| Both wrong | 2 |
| Full only correct (lost after removing brief) | **3** |
| No-brief only correct | **1** |

Lost after brief removal:
- `pilot_task7_User10_seed0`
- `pilot_task9_User9_seed0`
- `pilot_task14_User14_seed0`

Gained after brief removal (nobrief only correct):
- `pilot_task17_User17_seed0`

### Recovery subset (Plan✓ Search✗ in full trajectory)
| | n | Write correct |
|---|---:|---:|
| Full | 8 | 7 |
| No-brief | 8 | 6 |

### Wave split (diagnostic only)
| Wave | n | Full Acc | No-brief Acc | Δ |
|---|---:|---:|---:|---:|
| Wave 1 (tasks 2,4,7,9,12) | 15 | 0.933 | 0.800 | −0.133 |
| Wave 2 (tasks 14,17,18,22,24) | 15 | 0.867 | 0.867 | 0.000 |
| **Pooled** | **30** | **0.900** | **0.833** | **−0.067** |

Wave 2 shows no net paired drop; the pooled estimate is therefore **weaker** than the pilot alone. Prefer pooled n=30 numbers in the paper.

### Quality note
- One short report: `ablation_nobrief_task2_User6_seed0` (948 chars; appears truncated / sources-only tail). Still attributed correctly as User6.
- Other reports were full-length (wave2 new reports ~6k–27k chars).

### Cost (observed, n=30 total)
| Item | Tokens / calls |
|---|---|
| Gemini input | 752,875 |
| Gemini output (incl. reasoning) | 234,589 |
| Gemini total | 987,464 |
| Solar write matches | 30 calls (cash ignored) |
| Est. Gemini cash | **~$0.25–0.80** (~350–1,100원; Flash-band proxy) |

### Interpretation
1. Removing the Planning brief **modestly reduces** Writing attribution on the paired n=30 slice (Δ=−0.067), but the task-bootstrap 95% CI **includes zero**.
2. Writing Acc remains **high (0.833)** without brief re-injection — well above chance (0.333) and comparable to the paper’s overall Writing Acc (0.800).
3. Therefore re-injection **helps at most partially and is not a pure tautology**: residual persona signal survives in findings/messages/writing synthesis.
4. Absolute full-pipeline Acc on this seed-0 slice (0.900) is higher than global Writing Acc (0.800); treat absolute levels as slice-specific and emphasise the **paired residual accuracy** claim.

### Claim language safe to use
> On a 30-report write-only ablation (seed 0; 10 task groups), removing the Planning brief changed Writing Acc@1 from 0.900 to 0.833 (Δ=−0.067; task-bootstrap 95% CI [−0.167, 0.067]). Substantial Writing recoverability remains without brief re-injection, so recovery is not explained by re-injection alone.

### Claim language to avoid
- “Brief removal collapses Writing to Search-level accuracy” — **false** (0.833 ≫ 0.550).
- “Re-injection fully explains recovery” — **overclaim**.
- “Statistically significant collapse under brief removal” — CI includes 0 on n=30.

---

## Experiment B — Attribution ↔ personalization utility

### Protocol
- All **120** confirmatory final reports
- Judge: **GPT-4o-mini**, temperature 0, tool-forced scores
- Scores: content personalization (1–5), presentation personalization (1–5)
- Correlated with frozen Solar hard-negative stage attribution (`matches_hardneg_v1`)
- Outputs: `runs/confirmatory/utility_judge_gpt4omini/`
- Summary: `utility_summary.json`

### Scripts
- `scripts/utility_personalization_judge.py`

### Overall scores
| Metric | Value |
|---|---:|
| Mean content | 4.508 |
| Mean presentation | 4.508 |
| Mean combined | 4.508 |
| Score distribution | 5: 74, 4: 35, 3: 9, 2: 2 (same for both dimensions) |

**Important limitation:** content and presentation scores were **identical on all 120 reports**. The judge collapsed the two dimensions; treat results as a **single personalization score**, not two independent axes.

### Correlation with Writing Acc@1

| Group | n | Mean personalization |
|---|---:|---:|
| Write correct | 96 | **4.573** |
| Write wrong | 24 | **4.250** |
| Δ | | **+0.323** |
| Pearson r (write correct vs mean) | | **0.183** |
| Task-bootstrap 95% CI for Δ | | **[−0.020, 0.717]** |

### By trajectory pattern
| Pattern | n | Mean |
|---|---:|---:|
| all_correct_prefix | 62 | 4.613 |
| recovered (Plan✓ Search✗ Write✓) | 24 | 4.500 |
| write_correct_other | 10 | 4.500 |
| non_recovered | 8 | 4.250 |
| write_wrong_other | 16 | 4.250 |

### By stage correctness (mean personalization)
| Stage | Correct mean (n) | Wrong mean (n) | Δ |
|---|---:|---:|---:|
| Plan | 4.526 (97) | 4.435 (23) | +0.091 |
| Search | 4.545 (66) | 4.463 (54) | +0.082 |
| Compress | 4.521 (71) | 4.490 (49) | +0.031 |
| Write | 4.573 (96) | 4.250 (24) | +0.323 |

### Seed instability
| Seed | Write✓ n | Write✗ n | Δ (correct − wrong) |
|---|---:|---:|---:|
| 0 | 49 | 11 | **−0.014** |
| 1 | 47 | 13 | **+0.617** |

### Cost (observed)
| Item | Value |
|---|---|
| GPT calls | 120 |
| Input tokens | 535,967 |
| Output tokens | 14,012 |
| Est. GPT cash | **~$0.06–0.09** |

### Interpretation
1. There is a **weak positive association** between Writing attribution correctness and personalization score (r≈0.18; mean gap +0.32).
2. The association is **not robust**: task-bootstrap CI for Δ includes ~0; seed0 shows essentially null, seed1 drives the gap.
3. Strong **ceiling effect** (most scores 4–5) compresses variance and weakens correlation tests.
4. Stage Acc at Search/Compress barely separates utility scores (Δ≤0.08), consistent with attribution measuring **recoverability**, not end-to-end personalization quality.
5. Safe scientific conclusion: **attribution recoverability is only a weak proxy for judged personalization utility** under this cheap judge.

### Claim language safe to use
> Across 120 reports, GPT-4o-mini personalization scores are high overall (mean 4.51/5). Reports with correct Writing attribution score 0.32 points higher on average than incorrect ones (4.57 vs 4.25; r=0.18), but the gap is unstable across seeds and its task-bootstrap interval includes zero. Attribution localizes persona recoverability; it is not a substitute for personalization utility evaluation.

---

## Combined implications for DRA-PULSE

| Prior concern | Evidence from these runs |
|---|---|
| Writing recovery is pure re-injection tautology | **Partially refuted.** n=30 no-brief Writing Acc stays high (0.833); pooled Δ modest and CI includes 0. |
| Attribution may not track personalization utility | **Supported as weak coupling.** Small/unstable positive association; ceilinged judge. |
| Need multi-backbone for mechanism claim | Still optional; within-backbone no-brief already softens tautology critique. |

### Recommended manuscript updates
1. Add a short **Write-only no-brief control** paragraph in Analysis with **n=30** paired numbers (not pilot-only).
2. Add **utility correlation** as exploratory evidence that Acc@1 ≠ utility; keep claim boundary.
3. Do **not** claim statistically significant collapse under brief removal (CI includes 0).
4. Note GPT judge dimension collapse and ceiling as limitations.

### Optional next steps (only if budget/time)
1. ~~Expand no-brief to n=30~~ **done**. Optional n=45–60 only if a tighter CI is needed for camera-ready.
2. Re-run utility with stricter rubric / forced differentiation of content vs presentation, or human spot-check 20 reports.
3. Equal-budget Solar rematch (cash 0) still optional hygiene (no dedicated CLI flag yet).

---

## File index

| Path | Role |
|---|---|
| `scripts/write_only_nobrief.py` | Gemini write-only generator |
| `scripts/analyze_nobrief_paired.py` | paired full vs nobrief Acc + bootstrap |
| `scripts/utility_personalization_judge.py` | GPT utility judge |
| `scripts/candidate_protocol.py` | `canonical_pilot_run_id` helper |
| `scripts/llm_matcher.py` | `nobrief` / `full_control` shuffle mapping |
| `runs/ablation/nobrief_writeonly/` | no-brief artifacts + batch summary |
| `runs/ablation/nobrief_writeonly/matches/` | Solar write matches (n=30) |
| `runs/ablation/nobrief_writeonly/analysis_paired.json` | paired full vs nobrief (n=30) |
| `runs/confirmatory/utility_judge_gpt4omini/` | 120 utility JSONs |
| `runs/confirmatory/utility_judge_gpt4omini/utility_summary.json` | aggregate correlation |

## Total estimated cash

| Component | Est. USD | Est. KRW (@1380) |
|---|---:|---:|
| Gemini no-brief **n=30** | 0.25–0.80 | 350–1,100 |
| GPT utility 120 | 0.06–0.09 | 80–130 |
| Solar matches | 0 (ignored) | 0 |
| **Total** | **~$0.3–0.9** | **~400–1,200원** |


---

## Experiment C — Equal character-budget rematch (seed 0)

See `equal_budget_control.md` for full detail.

| Stage | Default | Equal 3500 | Δ |
|---|---:|---:|---:|
| Plan | 0.800 | 0.800 | 0.000 |
| Search | 0.533 | 0.517 | −0.017 |
| Compress | 0.567 | 0.600 | +0.033 |
| Write | 0.817 | 0.800 | −0.017 |

Dip preserved. Cash: 0 (Solar).

---

## Experiment B′ — Utility judge v2 (re-run)

- Dir: `runs/confirmatory/utility_judge_gpt4omini_v2/`
- Rubric: forced independent content/presentation evidence + anti-ceiling
- n=120 GPT-4o-mini

| Metric | v1 | v2 |
|---|---:|---:|
| Mean content | 4.508 | 4.008 |
| Mean presentation | 4.508 | 3.650 |
| Frac identical axes | 1.000 | 0.608 |
| Write✓−Write✗ Δ | +0.323 | +0.099 |
| Pearson r | 0.183 | 0.151 |
| Δ bootstrap CI | [−0.02, 0.72] | [−0.02, 0.23] |

v2 reduces dimension collapse and ceiling somewhat, but attribution–utility
coupling remains weak/non-robust. Prefer v2 numbers in the paper.

### Proxy spot-check n=20 (NOT independent human)

- Files: `utility_human_spotcheck_20.md`, `utility_proxy_spotcheck_20.json`
- Annotator: project AI assistant, single-pass persona+report reading
- **Do not cite as human validation**

| Metric | Proxy n=20 |
|---|---:|
| Mean content / presentation / mean | 3.80 / 3.60 / 3.70 |
| Frac identical axes | 0.60 |
| Write✓ vs Write✗ mean | 4.21 vs 2.94 (Δ=+1.27) |
| Pearson r (write vs mean) | 0.67 |

Interpretation: proxy scores are less ceilinged than GPT-v1 and flag clear
mismatches (e.g., café owner / clinical psych receiving album guides at 2/2).
The large Write✓ gap may partly reflect non-blind scoring; treat as
exploratory consistency check only.
