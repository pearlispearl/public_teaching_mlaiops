"""Export a trained model to a local file, for canary testing.

Unlike scripts/export_model.py (which is CI-only and not for submission), this script
takes n_estimators as an argument so we can produce two model artifacts — a good one and
a deliberately-worse one — for the canary/rollback exercise in Task 4.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
from sklearn.ensemble import RandomForestClassifier

from src import config, data, seeds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("reports/model.joblib"))
    ap.add_argument("--seed", type=int, default=seeds.DEFAULT_SEED)
    ap.add_argument("--n-estimators", type=int, default=200)
    ap.add_argument("--max-depth", type=int, default=8)
    ap.add_argument("--min-samples-leaf", type=int, default=5)
    args = ap.parse_args()

    cfg = config.load(strict=False)
    seed = seeds.set_all(args.seed)
    df = data.load_raw(cfg.raw_path)
    train_df, _, _ = data.split(df, seed=seed)

    model = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        random_state=seed,
        n_jobs=1,
    )
    model.fit(train_df[data.FEATURES], train_df[data.TARGET])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.out)
    print(f"wrote {args.out} (n_estimators={args.n_estimators})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
