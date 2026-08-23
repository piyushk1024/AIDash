[cleaned_Diwali_sales.csv] loading into Postgres as "cleaned_diwali_sales"...
  [cost] profiling via Dasher pipeline...
  [cost] naive: reading 1000 raw rows...
  [pipeline] running semantics -> plan -> build (with self-healing)...
  [judge] scoring 6 built charts...

---
## Eval Report — `cleaned_Diwali_sales.csv`

Rows: 11,251 | Naive row limit: 1000 | Model: `gemini/gemini-3.1-flash-lite`

### Cost faceoff: Dasher profile vs naive row-dump

| | Dasher (profile) | Naive (1000 rows) |
|---|---|---|
| Input tokens  | 8,915 | 64,672 |
| Output tokens | 899 | 858 |
| Cost (USD)    | $0.003577 | $0.017455 |
| Context chars | 17,441 | 95,425 |

**Naive used 7.3x more input tokens.** Dasher is O(columns); naive is O(rows x columns).

### Chart quality (LLM judge)

| Chart | Relevance | Correctness | Clarity | Justification |
|---|---|---|---|---|
| Total Revenue by Product Category | 5 | 5 | 5 | The chart addresses a fundamental business question regarding product performance, and the SQL correctly aggregates revenue by category with an appropriate horizontal bar chart layout. |
| Sales Volume by Gender and Marital Status | 5 | 3 | 4 | The SQL query performs a necessary grouping, but the chart fails to represent the 'Marital_Status' dimension (e.g., via stacking or grouping), essentially hiding a segment of the requested data in the final visualization. |
| Revenue Contribution by Top 5 States | 5 | 5 | 5 | The chart effectively surfaces a key business performance metric by identifying top-performing regions, and the SQL accurately implements the requested aggregation and top-N filtering. |
| Distribution of Customer Age | 5 | 4 | 5 | Understanding age demographics is critical for sales targeting; while the SQL uses a random sample rather than the full dataset, a histogram is the correct choice for visualizing continuous numerical distribution. |
| Revenue by Occupation Segment | 5 | 5 | 5 | Analyzing revenue by occupation is a standard and highly relevant business metric for retail sales data; the SQL query correctly aggregates the total amount by occupation, and the bar chart is the appropriate visualization for this categorical comparison. |
| Order Count by Zone and Age Group | 5 | 2 | 4 | The query is business-relevant and clearly titled, but the chart type 'tableg' is not a standard visualization format, and the SQL performs a pivot-like aggregation that is best served by a heatmap or matrix rather than a simple table. |

**Averages** — relevance: 5.0, correctness: 4.0, clarity: 4.67
[deliveries.csv] loading into Postgres as "deliveries"...
  [cost] profiling via Dasher pipeline...
  [cost] naive: reading 1000 raw rows...
  [pipeline] running semantics -> plan -> build (with self-healing)...
  [judge] scoring 6 built charts...

[1;31mGive Feedback / Get Help: https://github.com/BerriAI/litellm/issues/new[0m
LiteLLM.Info: If you need to debug this error, use `litellm._turn_on_debug()'.


---
## Eval Report — `deliveries.csv`

Rows: 260,920 | Naive row limit: 1000 | Model: `gemini/gemini-3.1-flash-lite`

### Cost faceoff: Dasher profile vs naive row-dump

| | Dasher (profile) | Naive (1000 rows) |
|---|---|---|
| Input tokens  | 10,855 | 44,727 |
| Output tokens | 1,069 | 1,039 |
| Cost (USD)    | $0.004317 | $0.012740 |
| Context chars | 24,937 | 98,657 |

**Naive used 4.1x more input tokens.** Dasher is O(columns); naive is O(rows x columns).

### Chart quality (LLM judge)

| Chart | Relevance | Correctness | Clarity | Justification |
|---|---|---|---|---|
| Run Efficiency by Batting Team | 5 | 5 | 5 | The chart effectively calculates the scoring rate per ball for each team, providing a highly relevant performance metric for cricket analysis, and the SQL correctly aggregates the data for a row-based visualization. |
| Dismissal Breakdown | 5 | 5 | 5 | The chart effectively visualizes the distribution of dismissal types in cricket, using appropriate aggregation for categorical data and a clear, descriptive title. |
| Run Contribution by Extras Type | 4 | 5 | 5 | The chart provides a useful breakdown of how different types of extras contribute to the total score, which is a standard analysis for cricket match performance. The SQL is correct for the stated objective and the bar chart is the appropriate visualization for categorical aggregated data. |
| Wicket Probability by Over | 5 | 5 | 5 | The chart provides a highly relevant analysis of scoring patterns in cricket by calculating the average dismissal rate per over. The SQL correctly implements the aggregation, and the line chart is the ideal visualization for trend analysis over a continuous variable like overs. |
| Average Runs per Over | 5 | 5 | 5 | The chart provides a standard and highly relevant metric for cricket analysis, using a correct aggregation (average per over) that is perfectly suited for a bar chart visualization. |
| Total Balls Recorded | 2 | 2 | 5 | While the chart accurately counts the total number of deliveries, it is a vanity metric with little actionable business value for a dashboard. Additionally, 'scalarg' is not a standard chart type, making a simple numeric display more appropriate. |

**Averages** — relevance: 4.33, correctness: 4.5, clarity: 5.0
