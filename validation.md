# Dasher Validation Log

Validation run: May 2025  
Method: Results verified against pandas ground truth on the same CSV files.  
"Correct" means the chart or insight value matches the computed ground truth.

---
## Datasets Used

| File | Source | Rows | Domain |
|---|---|---|---|
| employee_data.csv | Kaggle | 400 | HR / compensation |
| matches.csv | Kaggle (IPL) | 1,095 | Sports analytics |
| distributed_system_architecture_stress_dataset.csv | Kaggle | — | SRE / platform engineering |

## Chart Accuracy

| Dataset | Domain | Rows | Rendered | Correct | Notes |
|---|---|---|---|---|---|
| employee_data | HR | 400 | 5/5 | 5/5 | Clean pass |
| distributed_system_architecture_stress | SRE / Platform | — | 6/6 | 5/6 | `avg` on `num_services` semantically imprecise |
| matches (IPL) | Sports | 1,095 | 6/6 | 4/6 | Currency formatting on margin scalar; venue column too high-cardinality to chart usefully |

**14/17 correct across 3 datasets.**

---

## NL Insight Accuracy

| Dataset | Question | Pass | Mode | Notes |
|---|---|---|---|---|
| Employee | Who are the highest paid employees? | ✓ | query | Minor: 4th highest is Cloud Solutions Architect, not IT Manager |
| Employee | Is there a salary gap by gender? | ✓ | stats | Exact values correct |
| Employee | Which position has most experience? | ✓ | stats | Exact values correct |
| IPL matches | Which team has won the most matches? | ✓ | query | All top 5 values exact |
| IPL matches | Does winning the toss correlate with winning? | ✗ | stats | Hallucinated correlation — toss win rate is 50.6%, effectively random |
| IPL matches | Which venue has highest avg target runs? | ✓ | query | Correct venue and value |
| Distributed systems | Avg latency: cascading failure vs healthy? | ✗ | stats | Cited degraded state (282ms) instead of cascading failure (564ms) |
| Distributed systems | Which root cause has highest error rate? | ✓ | stats | Exact values correct |
| Distributed systems | Circuit breaker rate: microservices vs monolith? | ✗ | stats | Direction correct, percentage conversion wrong |

**5.5/9 correct.**

---

## Known Limitations

1. **Boolean columns passed to `avg` aggregation** — causes chart render failure (seen on API failure dataset)
2. **Numeric-but-categorical columns** (e.g. HTTP status codes) misclassified as measures by Gemini
3. **High-cardinality dimensions** (e.g. `batter`, `venue`) not consistently marked non-chartable
4. **Stats mode cross-column reasoning** — Gemini infers correlations between columns without the profile containing joint distributions; unreliable for relational questions
5. **Heterogeneous column handling** — fragile on IPL deliveries wickets column
6. **Metabase currency auto-formatting** — numeric columns rendered with $ prefix in some cases

---

## Recommended Best Practice (Insights)

Until prompt improvements are shipped, treat insights as **directional exploration, not authoritative reporting**. Stats mode is reliable for single-column summaries (means, counts, top values). Cross-column comparisons and correlation questions are better served by query mode but not guaranteed — verify against source data for any decision-relevant finding.
