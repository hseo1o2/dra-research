# Human personalization spot-check (n=20)

Date: 2026-08-05
**Annotator:** independent human annotator, single pass.

## Rubric (1–5)
- **Content**: topics/constraints/recommendations match the user.
- **Presentation**: tone/depth/jargon/structure match background.

## Summary
- Mean content / presentation / combined: **3.8 / 3.6 / 3.7**
- Identical axes: **60%** (vs v1 100%, v2 60.8%)
- Write✓ mean vs Write✗ mean: **4.208 vs 2.938** (Δ=1.271)
- Pearson r (write correct vs human mean): **0.671**
- Human vs v1 mean Pearson r: **0.518**
- Fraction within 0.5 of GPT-v2 mean: **0.6**

| # | run_id | pattern | Write✓ | v1 | v2 c/p | human c/p | notes |
|---:|---|---|:---:|---:|---|---|---|
| 1 | `pilot_task27_User14_seed1` | all_correct_prefix | Y | 5.0 | 4/3 | **5/4** | Illustrator+album: visual-first marketing and ¥20k studio fit; structure is solid pro guid |
| 2 | `pilot_task2_User7_seed0` | all_correct_prefix | Y | 5.0 | 4/4 | **5/5** | New-media CSS exchange plan matches Beijing journalism/Python grad student almost perfectl |
| 3 | `pilot_task43_User10_seed1` | all_correct_prefix | Y | 5.0 | 4/4 | **5/4** | Non-compete analysis for foreign-enterprise marketing manager in Shanghai; strong role/loc |
| 4 | `pilot_task43_User18_seed0` | all_correct_prefix | Y | 4.0 | 4/3 | **4/3** | Data-analyst non-compete is on-target topic-wise; presentation is statute-heavy legal memo |
| 5 | `pilot_task29_User18_seed0` | non_recovered | N | 4.0 | 4/3 | **3/3** | Healthy fast-food Shanghai plan is a plausible side venture but barely uses analyst identi |
| 6 | `pilot_task29_User18_seed1` | non_recovered | N | 4.0 | 4/3 | **3/3** | Same task, similar: market analysis present but still white-collar F&B template more than  |
| 7 | `pilot_task17_User17_seed0` | non_recovered | N | 5.0 | 4/4 | **4/4** | Multi-gen Qingdao/Weihai plan fits head nurse with teens+elders; nursing profession lightl |
| 8 | `pilot_task17_User17_seed1` | non_recovered | N | 5.0 | 4/4 | **4/4** | Parallel multi-gen beach plan; good family constraints, presentation clear/practical for b |
| 9 | `pilot_task7_User18_seed1` | recovered | Y | 4.0 | 4/4 | **3/3** | AI EdTech startup blueprint for data analyst is only loosely career-aligned (product pivot |
| 10 | `pilot_task27_User14_seed0` | recovered | Y | 5.0 | 4/4 | **5/4** | Album plan explicitly leverages illustrator visual advantage and budget/time constraints;  |
| 11 | `pilot_task22_User18_seed0` | recovered | Y | 5.0 | 4/4 | **5/5** | Shanghai 25–30F data-analyst pension/insurance plan names persona constraints (Hefei paren |
| 12 | `pilot_task12_User5_seed1` | recovered | Y | 5.0 | 4/4 | **5/5** | Emotion regulation as control/feedback system is extremely well matched to mechanical auto |
| 13 | `pilot_task14_User14_seed1` | recovered | Y | 5.0 | 4/4 | **5/4** | Marathon plan customized to Shanghai illustrator + yoga/pilates/hiking; presentation pract |
| 14 | `pilot_task7_User10_seed0` | write_correct_other | Y | 4.0 | 4/3 | **4/3** | AI HE platform for marketing manager has strategy/market research fit; heavy generic start |
| 15 | `pilot_task24_User12_seed0` | write_correct_other | Y | 5.0 | 4/4 | **3/4** | Xiamen coastal home insurance vs Beijing Haidian AI entrepreneur residence is partial task |
| 16 | `pilot_task24_User12_seed1` | write_correct_other | Y | 5.0 | 5/4 | **4/4** | Richer product comparison for high-value electronics; still coastal Xiamen premise, but mo |
| 17 | `pilot_task7_User10_seed1` | write_wrong_other | N | 3.0 | 4/3 | **3/3** | AI startup blueprint when Write✗: competent generic strategy, weak marketing-manager / fam |
| 18 | `pilot_task27_User13_seed0` | write_wrong_other | N | 4.0 | 4/3 | **2/2** | Café owner / single mother receives indie album production guide—topic largely ignores caf |
| 19 | `pilot_task27_User13_seed1` | write_wrong_other | N | 5.0 | 4/4 | **2/3** | Same album task in Chinese: still music not café; presentation slightly more accessible in |
| 20 | `pilot_task27_User2_seed1` | write_wrong_other | N | 5.0 | 4/4 | **2/2** | Clinical psych grad student gets music album gear guide; almost no psychology/persona hook |

## Interpretation
- Human scores use a wider range than GPT-v1 and often lower presentation than content.
- Write-correct reports score higher on average (n=20).
- Largest mismatches are Creative album tasks for café owner / clinical psych (scores 2/2).
- Strongest fits: CSS exchange (User7), engineer emotion-regulation framing (User5), analyst pension plan (User18 finance).

## Status
- [x] Human labels completed
