"""Recompute the THB columns of the Task 9 tables from saved eval reports.

    python scripts/reprice_llm_reports.py

Reads reports/llm_eval-work_order-*.json (token counts the provider reported, not
re-measured here) and prices them with the current rates in src/llmcost.py. No cloud calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import llmcost  # noqa: E402


def main() -> int:
    files = sorted(Path("reports").glob("llm_eval-work_order-*.json"))
    if not files:
        print("No reports/llm_eval-work_order-*.json found. Run from the repo root.")
        return 1
    print(f"{'file':<58} {'pass':>7} {'in':>5} {'out':>4} {'THB/1k old':>11} {'THB/1k new':>11}")
    for path in files:
        rep = json.loads(path.read_text())
        usage = llmcost.Usage(rep["avg_input_tokens"], rep["avg_output_tokens"])
        new = llmcost.cost_per_1k_requests(rep["provider"], rep["model"], usage)
        print(f"{path.name:<58} {rep['passed']:>2}/{rep['cases']:<4} "
              f"{usage.input_tokens:>5} {usage.output_tokens:>4} "
              f"{rep['thb_per_1k_requests']:>11.4f} {new:>11.4f}")
    print(f"\nrates: {llmcost.token_rates('gcp', 'small')} THB per 1M tokens (in, out); "
          f"cache read factor {llmcost.CACHE_READ_FACTOR}, "
          f"break-even {llmcost.cache_breakeven_hit_rate('gcp', 'small', 1000):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
