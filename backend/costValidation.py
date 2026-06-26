"""
costValidation.py — Dashboard creation: Dasher profiling vs naive row-passing

Tests the core architectural claim:
  Dasher sends O(columns) statistical summary to the LLM for semantic inference.
  Naive sends raw CSV rows directly. Row count should not affect Dasher's token usage.

Usage:
    python costValidation.py --csv path/to/file.csv --rows 500

Requires LLM_API_KEY and LLM_MODEL in .env or environment.

Output: markdown table ready to paste into VALIDATION.md or README.
"""

import argparse
import json
import sys
from pathlib import Path

import litellm
import pandas as pd
from dotenv import load_dotenv

from app.config import settings
from app.services.profiler import profile_csv
from app.services.llmClient import build_semantics_prompt

load_dotenv()

# Verify pricing at your provider's docs before running
PRICE_PER_1M_INPUT  = 0.10   # USD
PRICE_PER_1M_OUTPUT = 0.40   # USD


def call_llm(prompt: str) -> dict:
    response = litellm.completion(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=settings.LLM_API_KEY,
    )
    input_tokens  = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost = (
        (input_tokens  / 1_000_000) * PRICE_PER_1M_INPUT +
        (output_tokens / 1_000_000) * PRICE_PER_1M_OUTPUT
    )
    return {
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "cost_usd":      round(cost, 6),
        "response":      response.choices[0].message.content.strip(),
    }


def run_dasher(csv_path: Path) -> dict:
    """Profile with pandas, send summary to LLM."""
    print("  Building profile...")
    profile  = profile_csv(csv_path, dataset_id="faceoff")
    context  = f"Dataset profile (statistical summary):\n{json.dumps(profile, indent=2)}"
    prompt   = build_semantics_prompt(context)
    result   = call_llm(prompt)
    result["context_chars"] = len(context)
    result["approach"]      = "Dasher (profile)"
    return result


def run_naive(csv_path: Path, max_rows: int) -> dict:
    """Send raw CSV rows directly to LLM."""
    print(f"  Reading {max_rows} raw rows...")
    df      = pd.read_csv(csv_path, encoding="utf-8-sig").head(max_rows)
    context = f"Raw dataset ({max_rows} rows):\n{df.to_csv(index=False)}"
    prompt  = build_semantics_prompt(context)
    result  = call_llm(prompt)
    result["context_chars"] = len(context)
    result["approach"]      = f"Naive ({max_rows} rows)"
    return result


def score_semantics(response_text: str, csv_path: Path) -> str:
    """
    Rough quality check — did the LLM identify the right number of columns?
    Returns a short pass/fail string for the table.
    """
    try:
        raw = response_text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
        all_cols = (
            parsed.get("date_columns", []) +
            parsed.get("dimensions",   []) +
            parsed.get("measures",     []) +
            parsed.get("flags",        []) +
            parsed.get("identifiers",  []) +
            parsed.get("unknown",      [])
        )
        df         = pd.read_csv(csv_path, encoding="utf-8-sig", nrows=1)
        expected   = len(df.columns)
        classified = len(all_cols)
        match      = "✓" if classified == expected else f"⚠ {classified}/{expected} cols"
        grain      = parsed.get("dataset_grain", "—")
        return f"{match} - grain: {grain}"
    except Exception as e:
        return f"✗ parse error: {e}"


def print_report(dasher: dict, naive: dict, csv_path: Path, max_rows: int):
    total_rows = len(pd.read_csv(csv_path, encoding="utf-8-sig"))
    ratio      = round(naive["input_tokens"] / dasher["input_tokens"], 1)
    cost_ratio = round(naive["cost_usd"] / dasher["cost_usd"], 1) if dasher["cost_usd"] else "—"

    dasher_quality = score_semantics(dasher["response"], csv_path)
    naive_quality  = score_semantics(naive["response"],  csv_path)

    print(f"\n---\n")
    print(f"## Cost Faceoff: Dashboard Semantic Inference\n")
    print(f"Dataset: `{csv_path.name}` — {total_rows:,} rows  ")
    print(f"Naive row limit: {max_rows}  ")
    print(f"Model: `{settings.LLM_MODEL}`  ")
    print(f"Pricing: input ${PRICE_PER_1M_INPUT}/1M | output ${PRICE_PER_1M_OUTPUT}/1M\n")

    print("| | Dasher (profile) | Naive ({} rows) |".format(max_rows))
    print("|---|---|---|")
    print(f"| Input tokens     | {dasher['input_tokens']:,} | {naive['input_tokens']:,} |")
    print(f"| Output tokens    | {dasher['output_tokens']:,} | {naive['output_tokens']:,} |")
    print(f"| Cost (USD)       | ${dasher['cost_usd']:.6f} | ${naive['cost_usd']:.6f} |")
    print(f"| Context chars    | {dasher['context_chars']:,} | {naive['context_chars']:,} |")
    print(f"| Token ratio      | 1x (baseline) | {ratio}x |")
    print(f"| Cost ratio       | 1x (baseline) | {cost_ratio}x |")
    print(f"| Semantics quality| {dasher_quality} | {naive_quality} |")

    print(f"\n**Naive approach used {ratio}x more input tokens for {max_rows} rows.**")
    print(f"Dasher token usage is O(columns). Naive is O(rows × columns).")
    print(f"At full dataset scale ({total_rows:,} rows), naive would be impractical.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",  required=True, help="Path to CSV file")
    parser.add_argument("--rows", type=int, default=1000,
                        help="Max rows to send in naive approach (default 1000)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nCost faceoff: {csv_path.name}")
    print(f"Naive row limit: {args.rows}\n")

    print("Running Dasher approach...")
    dasher = run_dasher(csv_path)

    print("Running naive approach...")
    naive = run_naive(csv_path, args.rows)

    print_report(dasher, naive, csv_path, args.rows)


if __name__ == "__main__":
    main()