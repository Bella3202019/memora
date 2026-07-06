# Eval comparison: v1 (gpt-5.2) -> v2 (gpt-5.2)

Baseline: 2026-07-05T18:17:51 (3 trials) · Candidate: 2026-07-05T18:20:04 (3 trials) · judge deepseek:deepseek-chat

| case | F1 v1 (gpt-5.2) | F1 v2 (gpt-5.2) | Δ F1 | halluc. v1 (gpt-5.2) | halluc. v2 (gpt-5.2) |
|---|---|---|---|---|---|
| simple-explicit | 1.000 | 1.000 | · +0.000 | 0 | 0 |
| multi-experience-separation | 0.739 | 1.000 | ▲ +0.261 | 2.33 | 0 |
| implied-emotion-no-truth | 0.831 | 1.000 | ▲ +0.169 | 3.33 | 0 |
| reflection-heavy | 0.778 | 0.667 | ▼ -0.111 | 2 | 1 |
| distractors-hypotheticals | 0.582 | 0.889 | ▲ +0.307 | 3.67 | 1 |
| mundane-minimal | 1.000 | 1.000 | · +0.000 | 0 | 0 |
| negation-not-occurrence | 0.848 | 1.000 | ▲ +0.152 | 1.67 | 0 |
| media-secondhand | 0.667 | 0.667 | · +0.000 | 3 | 1 |
| dream-boundary | 0.755 | 1.000 | ▲ +0.245 | 3.67 | 0 |
| bilingual-mixed | 1.000 | 1.000 | · +0.000 | 0 | 0 |
| long-entry-relationships | 1.000 | 1.000 | · +0.000 | 0 | 0 |
| emotion-only-venting | 0.667 | 1.000 | ▲ +0.333 | 2 | 0 |
| past-recollection-guard | 0.941 | 0.852 | ▼ -0.089 | 0.67 | 1 |
| future-vs-real-action-guard | 0.926 | 0.889 | ▼ -0.037 | 0.67 | 1 |

**Overall F1:** 0.838 -> 0.926 (+0.088)
**Hallucinations/trial:** 23.0 -> 5.0
**Schema violations:** 1 -> 0
