# app/services/agentTools.py
from app.schemas.chartTypes import CHART_TYPE_VALUES, CHART_TYPE_GUIDANCE

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_data",
            "description": (
                "Execute a read-only SQL query to investigate the dataset. "
                "Use this to understand patterns, distributions, or anomalies "
                "before deciding which charts to build. Results are capped at 20 rows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A PostgreSQL SELECT query. Must be aggregate-focused "
                            "(use GROUP BY, COUNT, AVG, SUM, RANK, etc.). "
                            "No semicolons. Double-quote all table and column names. "
                            "Boolean columns cannot be passed directly to SUM/AVG — "
                            "cast first, e.g. SUM(CASE WHEN \"flag_col\" THEN 1 ELSE 0 END)."
                        ),
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "One sentence: what you are investigating and why.",
                    },
                },
                "required": ["sql", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_and_add_chart",
            "description": (
                "Build a chart from a SQL query and add it to the dashboard. "
                "Call this when you have decided what to visualise, "
                "ideally after inspecting the data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_title": {
                        "type": "string",
                        "description": "A descriptive title for the chart.",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": CHART_TYPE_VALUES,
                        "description": (
                            "Must match the SQL output shape and the chart's analytical "
                            "intent. See guidance below for how to pick and how to "
                            "configure each type:\n" + CHART_TYPE_GUIDANCE
                        ),
                    },
                    "sql": {
                        "type": "string",
                        "description": (
                            "PostgreSQL SELECT query. No semicolons. "
                            "Double-quote all table and column names. "
                            "Alias all output columns clearly. "
                            "Boolean columns cannot be passed directly to SUM/AVG — "
                            "cast first, e.g. SUM(CASE WHEN \"flag_col\" THEN 1 ELSE 0 END)."
                        ),
                    },
                    "x_alias": {
                        "type": "string",
                        "description": "Exact alias of the dimension column in the SQL. Omit for scalar/table/passthrough types.",
                    },
                    "y_alias": {
                        "type": "string",
                        "description": "Exact alias of the measure column in the SQL. Omit for scalar/table/passthrough types.",
                    },
                    "series_alias": {
                        "type": "string",
                        "description": (
                            "Optional. Only for bar/row charts. Exact alias of a second "
                            "dimension to group or stack by within each x-axis category. "
                            "Use this instead of building separate charts when the goal "
                            "requires comparing across two dimensions at once."
                        ),
                    },
                    "viz_params": {
                        "type": "object",
                        "description": (
                            "Required for gauge, funnel, waterfall, and map chart "
                            "types. A dict of Plotly trace fields matching what that "
                            "chart type needs (e.g. gauge steps/bands for gauge). "
                            "You decide the values yourself, typically by computing "
                            "them via inspect_data first. Omit for all other chart types."
                        ),
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "One sentence: what this chart shows and how it serves the goal.",
                    },
                },
                "required": ["chart_title", "chart_type", "sql", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Call this when the dashboard goal has been satisfied. "
                "Provide a summary of what was built and why it addresses the goal."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was built and how it addresses the goal.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an expert BI analyst. Build a dashboard that satisfies the goal below.

Table: "{table_name}"

Available columns (name | base_type | semantic_role):
{field_reference}

Dataset profile (column stats):
{profile_summary}

Goal: {goal}

Rules:
- Use inspect_data to investigate the data before building charts. Let what you find shape what you build.
- Use build_and_add_chart to add charts that directly address the goal.
- Build as many charts as the goal genuinely requires — don't build a chart just
  to hit a count. A narrow goal may need only 2-3 charts; a genuinely multi-faceted
  one may need more.
- When the goal involves multiple factors together (e.g. "does X affect Y after
  accounting for Z"), prefer one chart that combines the relevant dimensions
  (see series_alias below) over several charts that each address only one factor.
- Call finish when the goal is satisfied.
- All SQL: double-quote all table and column names, PostgreSQL syntax, no semicolons.
- Boolean columns cannot be passed directly to SUM/AVG — cast first, e.g.
  SUM(CASE WHEN "flag_col" THEN 1 ELSE 0 END), never SUM("flag_col").
- Inspection queries must be aggregate-focused — never SELECT *.

Chart type guidance:
{chart_type_guidance}
"""