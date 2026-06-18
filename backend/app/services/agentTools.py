# app/services/agentTools.py

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
                            "No semicolons. Double-quote all table and column names."
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
                        "enum": ["bar", "line", "scalar", "pie"],
                        "description": (
                            "Must match the SQL output shape: "
                            "'scalar' for exactly one row and one column; "
                            "'bar', 'line', or 'pie' for a dimension column followed by a measure column."
                        ),
                    },
                    "sql": {
                        "type": "string",
                        "description": (
                            "PostgreSQL SELECT query. No semicolons. "
                            "Double-quote all table and column names. "
                            "Alias all output columns clearly."
                        ),
                    },
                    "x_alias": {
                        "type": "string",
                        "description": "Exact alias of the dimension column in the SQL. Omit for scalar.",
                    },
                    "y_alias": {
                        "type": "string",
                        "description": "Exact alias of the measure column in the SQL. Omit for scalar.",
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

SYSTEM_PROMPT = """You are an expert BI analyst. Build a Metabase dashboard that satisfies the goal below.

Table: "{table_name}"

Available columns (name | base_type | semantic_role):
{field_reference}

Dataset profile (column stats):
{profile_summary}

Goal: {goal}

Rules:
- Use inspect_data to investigate the data before building charts. Let what you find shape what you build.
- Use build_and_add_chart to add charts that directly address the goal.
- Build between 3 and 5 charts total.
- Call finish when the goal is satisfied.
- All SQL: double-quote all table and column names, PostgreSQL syntax, no semicolons.
- chart_type must match the SQL output: scalar for one row/one column, bar/line/pie for dimension + measure.
- Inspection queries must be aggregate-focused — never SELECT *.
"""