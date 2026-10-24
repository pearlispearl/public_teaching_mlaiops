"""Lab 5 — the registration gate.

Compares a candidate against the currently registered production model. Exits non-zero
when the candidate should NOT be registered, which is what makes the pipeline condition
real rather than decorative. With --decision-out it instead writes "pass" or "fail" to a
file and exits 0, so a pipeline can branch on the decision instead of aborting.

    python scripts/evaluation_gate.py --metrics reports/metrics.json

The thresholds below were measured, not chosen: `python scripts/measure_gate_noise.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Measured on this dataset, 20 resamples (scripts/measure_gate_noise.py), test ROC AUC:
#   model seed varies, data and split fixed : std 0.0015, range 0.0054
#   data split and model seed both vary     : std 0.0166, range 0.0521, worst 0.8229
#
# MIN_ABSOLUTE: 0.80 sits 0.02 below the worst healthy result seen, so a healthy model
#   never trips it, while a broken one (AUC near 0.5) does.
# MIN_IMPROVEMENT_PAIRED: candidate and incumbent were trained on the same data version,
#   so the only noise is the model seed. 0.005 is the full range seen (0.0054) rounded
#   down: a pure re-seed will not be promoted, a real gain of a few thousandths can be.
# MIN_IMPROVEMENT_UNPAIRED: the data changed, so the incumbent's stored metric came from a
#   different test split. Noise is then 0.0166 std and 0.033 is two standard deviations.
#   Zero would promote noise on every retrain; much more would block real gains.
MIN_ABSOLUTE = 0.80
MIN_IMPROVEMENT_PAIRED = 0.005
MIN_IMPROVEMENT_UNPAIRED = 0.033


def decide(candidate: float, incumbent: float | None, paired: bool) -> tuple[bool, str]:
    """(passes, reason). Pure function so it can be tested without a cloud account."""
    if candidate < MIN_ABSOLUTE:
        return False, f"below absolute floor {MIN_ABSOLUTE}"
    if incumbent is None:
        return True, "no incumbent registered; first registration"
    margin = MIN_IMPROVEMENT_PAIRED if paired else MIN_IMPROVEMENT_UNPAIRED
    delta = candidate - incumbent
    kind = "same data" if paired else "different data"
    if delta < margin:
        return False, (f"improvement {delta:+.4f} within noise ({kind}, required "
                       f"{margin:+.4f}); not registering")
    return True, f"improvement {delta:+.4f} meets the {kind} margin {margin:+.4f}"


def _clean(value: str) -> str:
    """Same normalisation the registry applies to label values."""
    return "".join(c if c.isalnum() or c == "-" else "-" for c in str(value).lower())[:63]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--metric", default="test_roc_auc")
    ap.add_argument("--incumbent", type=float, default=None,
                    help="override the registry lookup with a score (testing the gate)")
    ap.add_argument("--paired", action="store_true",
                    help="with --incumbent: treat it as measured on the same data version")
    ap.add_argument("--no-registry", action="store_true",
                    help="skip the registry lookup; treat as first registration")
    ap.add_argument("--decision-out", type=Path, default=None,
                    help="write 'pass' or 'fail' here and exit 0 (pipeline branching)")
    args = ap.parse_args()

    payload = json.loads(args.metrics.read_text())
    candidate = float(payload[args.metric])
    print(f"candidate {args.metric} = {candidate:.4f}")

    incumbent = args.incumbent
    paired = args.paired
    if incumbent is None and not args.no_registry:
        from cloudlayer.factory import get_adapter
        from src import config

        cfg = config.load()
        # register_model stores the test AUC under the lineage key "metric-test".
        key = "metric-test" if args.metric == "test_roc_auc" else args.metric.replace("_", "-")
        found = get_adapter(cfg).production_metric(cfg.model_registry_name, key)
        if found is not None:
            incumbent = found["metric"]
            fingerprint = payload.get("data_fingerprint")
            paired = bool(fingerprint) and _clean(fingerprint) == found["data_version"]
            print(f"registry: version {found['version']} data {found['data_version'][:12]}")

    passes, reason = decide(candidate, incumbent, paired)
    if incumbent is not None:
        print(f"incumbent {incumbent:.4f}  delta {candidate - incumbent:+.4f}")
    print(f"GATE {'PASS' if passes else 'FAIL'}  {reason}")

    if args.decision_out:
        args.decision_out.parent.mkdir(parents=True, exist_ok=True)
        args.decision_out.write_text("pass" if passes else "fail")
        return 0
    return 0 if passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
