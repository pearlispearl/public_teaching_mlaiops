"""Lab 4 post-mortem helper: how much does the injected drift change the model's output?

Trains the Lab 1 configuration on the training machines, then scores the validation machines
before and after the same shift/scale that scripts/inject_drift.py applies to `temp_c`.
Labels are left unchanged, so this measures the effect on predictions, not on real outcomes.

    python scripts/estimate_drift_impact.py
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import data  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=Path("data/raw/sensors.csv"))
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--feature", default="temp_c")
    ap.add_argument("--cutoff", type=float, default=0.5, help="probability that counts as a flag")
    args = ap.parse_args()

    df = data.load_raw(args.csv)
    train, val, _ = data.split(df, seed=args.seed)
    model = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=5, random_state=args.seed, n_jobs=-1
    ).fit(train[data.FEATURES], train[data.TARGET])

    base = model.predict_proba(val[data.FEATURES])[:, 1]
    print(f"validation rows {len(val)}, mean risk {base.mean():.3f}, "
          f"flagged at >= {args.cutoff}: {np.mean(base >= args.cutoff):.2%}")

    def shift(x):
        return x + 6

    def scale(x):
        return x.mean() + (x - x.mean()) * 1.5

    for name, fn in (("shift +6", shift), ("scale x1.5", scale)):
        moved = val.copy()
        moved[args.feature] = fn(moved[args.feature])
        p = model.predict_proba(moved[data.FEATURES])[:, 1]
        print(f"{name:11s} mean risk {p.mean():.3f} ({p.mean() / base.mean() - 1:+.0%}), "
              f"flagged {np.mean(p >= args.cutoff):.2%}, "
              f"rows whose risk moves by more than 0.1: {np.mean(np.abs(p - base) > 0.1):.1%}")


if __name__ == "__main__":
    main()
