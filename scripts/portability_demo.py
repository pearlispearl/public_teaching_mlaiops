"""Lab 5 Task 4 Part B: demonstrate the second provider with a payload our service accepts.

    BLOB_URI=<second provider uri> REGION=<its region> CLOUD_PROVIDER=gcp \
      python scripts/portability_demo.py --second-provider aws --endpoint https://<service>/predict

`make swap-check` sends an empty payload that no real model accepts, so it cannot show an
invoke passing. This runs the same three calls with a valid sensor reading and prints the
model's answer, which is the evidence the lab asks for.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter  # noqa: E402
from src import config  # noqa: E402

PAYLOAD = {"temp_c": 75.0, "vibration_mm_s": 12.5, "pressure_kpa": 250.0,
           "hours_since_service": 120.0, "load_pct": 65.0, "ambient_humidity": 45.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--second-provider", required=True, choices=["aws", "azure", "gcp"])
    ap.add_argument("--endpoint", required=True, help="endpoint name or https URL of the service")
    args = ap.parse_args()

    primary = config.load(strict=False)
    if primary.provider == args.second_provider:
        print("The second provider must differ from CLOUD_PROVIDER.")
        return 1
    swapped = config.Config(**{**primary.__dict__, "provider": args.second_provider})
    adapter = get_adapter(swapped)
    print(f"primary {primary.provider}  second {args.second_provider}  blob {swapped.blob_uri}\n")

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.txt"
        probe.write_text("itcs355 portability probe\n")
        try:
            uri = adapter.upload(str(probe), "portability/probe.txt")
            print(f"[PASS] upload    -> {uri}")
            back = Path(tmp) / "back.txt"
            adapter.download(uri, str(back))
            same = back.read_text() == probe.read_text()
            print(f"[{'PASS' if same else 'FAIL'}] download  round trip identical: {same}")
            ok &= same
        except Exception as exc:
            print(f"[FAIL] storage   {type(exc).__name__}: {exc}")
            ok = False
        try:
            print(f"[PASS] invoke    -> {adapter.invoke(args.endpoint, PAYLOAD)}")
        except Exception as exc:
            print(f"[FAIL] invoke    {type(exc).__name__}: {exc}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
