"""Lab 5 Task 1 — measure the noise the registration gate has to sit above.

    python scripts/measure_gate_noise.py [--runs 20]

Trains the Lab 1 configuration repeatedly and reports test ROC AUC spread in two cases:
the model seed varies with data and split fixed, and the split and seed both vary. The
thresholds in scripts/evaluation_gate.py come from these numbers.
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from src import config, data, seeds


def test_auc(df, split_seed: int, model_seed: int) -> float:
    train_df, _, test_df = data.split(df, seed=split_seed)
    model = RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5,
                                   random_state=model_seed, n_jobs=-1)
    model.fit(train_df[data.FEATURES], train_df[data.TARGET])
    return float(roc_auc_score(test_df[data.TARGET],
                               model.predict_proba(test_df[data.FEATURES])[:, 1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    args = ap.parse_args()

    df = data.load_raw(Path(config.load(strict=False).raw_path))
    fixed = [test_auc(df, seeds.DEFAULT_SEED, s) for s in range(args.runs)]
    varied = [test_auc(df, s, s) for s in range(args.runs)]
    for name, values in (("model seed varies, split fixed", fixed),
                         ("split and model seed vary", varied)):
        print(f"{name:32s} mean {st.mean(values):.4f}  std {st.stdev(values):.4f}  "
              f"min {min(values):.4f}  max {max(values):.4f}  "
              f"range {max(values) - min(values):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
