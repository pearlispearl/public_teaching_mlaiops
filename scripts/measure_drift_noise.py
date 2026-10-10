"""How much PSI does ordinary sampling noise produce on THIS dataset?

A drift threshold is only justified if it sits above the PSI you get when nothing has
changed. This script measures that: it splits the data into a reference half and a pool,
draws many windows of a given size from the pool, and reports how large PSI gets by
chance alone. Run from the repository root:

    python scripts/measure_drift_noise.py
    python scripts/measure_drift_noise.py --windows 200 500 1000 --trials 1000

Pick the window size your scheduled drift job will actually see. PSI noise grows as the
window shrinks, so the same threshold means different things at different window sizes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    # Same pattern as monitoring/drift.py: make the repo root importable, then import.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from monitoring.drift import psi
    from src import data

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/raw/sensors.csv"))
    ap.add_argument("--windows", type=int, nargs="+", default=[200, 500, 1000, 2000])
    ap.add_argument("--trials", type=int, default=500)
    ap.add_argument("--quantile", type=float, default=0.99,
                    help="noise level to sit above (0.99 = exceeded by chance 1 run in 100)")
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()

    df = pd.read_csv(args.data)
    rng = np.random.default_rng(args.seed)

    # Row-level split. Rows from one machine are correlated, so real production windows
    # can be noisier than this: treat the result as a floor and add margin.
    order = rng.permutation(len(df))
    half = len(df) // 2
    reference = df.iloc[order[:half]]
    pool = df.iloc[order[half:]]

    print(f"reference rows={len(reference)}  pool rows={len(pool)}  "
          f"trials={args.trials}  quantile={args.quantile}")
    summary = []
    for w in args.windows:
        if w > len(pool):
            print(f"\nwindow {w}: skipped, larger than the pool ({len(pool)} rows)")
            continue
        rows = []
        worst = 0.0
        for feature in data.FEATURES:
            ref = reference[feature].to_numpy(dtype=float)
            scores = np.array([
                psi(ref, pool[feature].sample(w, random_state=int(rng.integers(1 << 31)))
                    .to_numpy(dtype=float))
                for _ in range(args.trials)
            ])
            q = float(np.quantile(scores, args.quantile))
            worst = max(worst, q)
            rows.append((feature, float(np.median(scores)), q, float(scores.max())))
        print(f"\nwindow = {w} rows")
        print(f"{'feature':<22}{'median':>9}{'p' + str(int(args.quantile * 100)):>9}{'max':>9}")
        for feature, med, q, mx in rows:
            print(f"{feature:<22}{med:>9.4f}{q:>9.4f}{mx:>9.4f}")
        summary.append((w, worst))

    print("\nNoise floor (highest per-feature quantile) by window size:")
    for w, worst in summary:
        print(f"  window {w:>5}: {worst:.4f}")
    print("\nThe threshold must be above the floor for YOUR window size, and below the PSI "
          "your injected drift (Task 6) produces. Check both before you commit to a number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
