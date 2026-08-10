[deliveries.csv] loading into Postgres as "deliveries"...
  [cost] profiling via Dasher pipeline...
  [cost] naive: reading 1000 raw rows...
  [pipeline] running semantics -> plan -> build (with self-healing)...
  [judge] scoring 6 built charts...

---
## Eval Report — `deliveries.csv`

Rows: 260,920 | Naive row limit: 1000 | Model: `gemini/gemini-3.1-flash-lite`

### Cost faceoff: Dasher profile vs naive row-dump

| | Dasher (profile) | Naive (1000 rows) |
|---|---|---|
| Input tokens  | 10,855 | 44,727 |
| Output tokens | 1,067 | 1,043 |
| Cost (USD)    | $0.001512 | $0.004890 |
| Context chars | 24,937 | 98,657 |

**Naive used 4.1x more input tokens.** Dasher is O(columns); naive is O(rows x columns).

### Chart quality (LLM judge)

| Chart | Relevance | Correctness | Clarity | Justification |
|---|---|---|---|---|
| Average Runs per Delivery by Team | 5 | 5 | 5 | The chart effectively compares scoring efficiency across teams, and the SQL correctly aggregates the mean runs per delivery grouped by team using a row chart, which is ideal for categorical comparisons. |
| Frequency of Dismissal Types | 5 | 5 | 5 | The chart effectively visualizes the distribution of dismissal methods, which is a key performance metric in cricket analytics; the SQL query accurately filters and aggregates the data for this purpose. |
| Total Wickets Taken by Bowling Team | 5 | 5 | 5 | The chart provides a direct and accurate ranking of bowling team performance by wicket count, using a highly readable horizontal bar chart (rowg) that effectively displays categorical data. |
| Average Runs Scored by Over | 5 | 5 | 5 | The chart effectively visualizes the scoring trend across the duration of an innings, which is a key performance metric in cricket analytics; the SQL and chart type are perfectly aligned for this time-series analysis. |
| Distribution of Total Runs per Ball | 4 | 3 | 5 | While a histogram is appropriate for this data, using a random sample of 5,000 rows instead of the entire dataset makes the distribution estimate potentially inaccurate; a simple frequency count would have been more robust. |
| Breakdown of Extras by Type | 5 | 5 | 5 | The chart effectively categorizes the source of extra runs, providing valuable operational insight into bowling discipline; the SQL and bar chart selection are perfectly suited for this categorical frequency distribution. |

**Averages** — relevance: 4.83, correctness: 4.67, clarity: 5.0
[cleaned_Diwali_sales.csv] loading into Postgres as "cleaned_diwali_sales"...
  [cost] profiling via Dasher pipeline...
  [cost] naive: reading 1000 raw rows...
  [pipeline] running semantics -> plan -> build (with self-healing)...
  [judge] scoring 6 built charts...

[1;31mGive Feedback / Get Help: https://github.com/BerriAI/litellm/issues/new[0m
LiteLLM.Info: If you need to debug this error, use `litellm._turn_on_debug()'.


[1;31mGive Feedback / Get Help: https://github.com/BerriAI/litellm/issues/new[0m
LiteLLM.Info: If you need to debug this error, use `litellm._turn_on_debug()'.


---
## Eval Report — `cleaned_Diwali_sales.csv`

Rows: 11,251 | Naive row limit: 1000 | Model: `gemini/gemini-3.1-flash-lite`

### Cost faceoff: Dasher profile vs naive row-dump

| | Dasher (profile) | Naive (1000 rows) |
|---|---|---|
| Input tokens  | 8,916 | 64,672 |
| Output tokens | 947 | 897 |
| Cost (USD)    | $0.001270 | $0.006826 |
| Context chars | 17,441 | 95,425 |

**Naive used 7.3x more input tokens.** Dasher is O(columns); naive is O(rows x columns).

### Chart quality (LLM judge)

| Chart | Relevance | Correctness | Clarity | Justification |
|---|---|---|---|---|
| Total Revenue by Product Category | 5 | 4 | 5 | The chart addresses a fundamental business question regarding revenue performance by category, though 'rowg' (row graph) is an unconventional label for what is standardly a horizontal bar chart. |
| Customer Demographic Split by Revenue | 5 | 4 | 5 | The chart effectively segments revenue by two key demographic variables; however, using a bar chart for a grouped/stacked metric can become cluttered if the legend is not explicitly handled or if the 'Gender' split is not visually distinct. |
| Sales Concentration by State | 5 | 4 | 5 | Analyzing order volume by state is highly relevant for business performance, and the SQL correctly aggregates the data; however, a 'rowg' (row graph) is a horizontal bar chart, which is highly readable for categorical data like state names. |
| Occupation vs. Average Order Value | 5 | 5 | 5 | Analyzing average order value by occupation is highly relevant for customer segmentation, and the SQL query perfectly aligns with the requested metrics and sorting logic. |
| Order Size Distribution | 4 | 2 | 5 | While understanding order distribution is relevant, the SQL uses a random sample of 5000 rows rather than the full dataset, which can misrepresent the actual distribution; additionally, a histogram is poor for a discrete variable with only 4 possible values (1-4), where a bar chart would be more accurate. |
| Revenue Flow: Zone to Product Category | 5 | 5 | 5 | A Sankey diagram is an excellent choice for visualizing the flow of revenue across two categorical dimensions, and the SQL correctly aggregates the sum of amounts for this relationship. |

**Averages** — relevance: 4.83, correctness: 4.0, clarity: 5.0
