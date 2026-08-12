"""
Auto-imported by Python at interpreter startup (sitecustomize hook).
Patches litellm.acompletion so no real LLM call happens during load testing.
Only active when DASHER_STUB_LLM=1 is set in the environment.
"""
import os

if os.environ.get("DASHER_STUB_LLM") == "1":
    import asyncio
    import json
    import litellm
    from types import SimpleNamespace

    _FAKE_SEMANTICS = {
        "dataset_id": "loadtest",
        "business_hint": None,
        "dataset_grain": "row",
        "date_columns": [],
        "dimensions": [
            {"column": "category", "semantic_role": "dimension", "confidence": 0.9, "chartable": True}
        ],
        "measures": [
            {"column": "value", "semantic_role": "measure", "confidence": 0.9, "chartable": True,
             "heterogeneous": False, "filter_column": None}
        ],
        "flags": [],
        "identifiers": [],
        "unknown": [],
        "notes": ["stubbed response for load test"],
    }

    _FAKE_PLAN = {
        "charts": [
            {"chart_type": "bar", "x_alias": "category", "y_alias": "value",
             "sql": "SELECT category, SUM(value) AS value FROM dataset GROUP BY category"}
        ]
    }

    def _fake_content(stage_hint: str) -> str:
        # dashboardPlanner and llmClient both call generate() with different
        # prompts; route by rough shape since stage isn't passed to acompletion.
        if "chart" in stage_hint.lower() or "plan" in stage_hint.lower():
            return json.dumps(_FAKE_PLAN)
        return json.dumps(_FAKE_SEMANTICS)

    async def _fake_acompletion(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt_text = messages[-1]["content"] if messages else ""
        content = _fake_content(prompt_text)

        await asyncio.sleep(0.05)  # rough floor to mimic network hop, not real LLM latency

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
            model="stub/loadtest",
        )

    litellm.acompletion = _fake_acompletion