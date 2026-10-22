"""Lab 5 Task 9 — measure the prompt-cache hit rate the provider actually reports.

    python scripts/measure_cache.py --system prompts/work_order_system.txt

Sends the golden prompts through the adapter twice with the same system prompt, reads
cached tokens from the provider's usage fields (never estimated), and compares the
measured hit rate with the break-even rate from src/llmcost.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config, llmcost


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", type=Path, default=Path("evals/golden/work_order.jsonl"))
    ap.add_argument("--system", type=Path, required=True)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--tier", default="small", help="price tier in src/llmcost.py")
    args = ap.parse_args()

    cfg = config.load()
    adapter = get_adapter(cfg)
    system = args.system.read_text()
    cases = [json.loads(line) for line in args.golden.read_text().splitlines() if line.strip()]

    total_in = cached = calls = 0
    for _ in range(args.passes):
        for case in cases:
            out = adapter.generate(case["prompt"], {
                "system": system, "temperature": 0.0, "max_output_tokens": 200,
                "json_output": True, "thinking_budget": 0,
            })
            total_in += out["input_tokens"]
            cached += out.get("cached_input_tokens", 0)
            calls += 1

    avg_in = round(total_in / calls)
    hit_rate = cached / total_in if total_in else 0.0
    breakeven = llmcost.cache_breakeven_hit_rate(cfg.provider, args.tier, avg_in)
    print(f"calls                 {calls}")
    print(f"avg input tokens      {avg_in}")
    print(f"cached input tokens   {cached} of {total_in}")
    print(f"measured hit rate     {hit_rate:.3f}")
    print(f"break-even hit rate   {breakeven:.3f}")
    verdict = "ABOVE break-even" if hit_rate > breakeven else "BELOW break-even"
    print(f"verdict               {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
