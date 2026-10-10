"""Scheduled drift check: fetch reference + current via the cloud layer, run drift --emit.

No provider SDK or URI scheme here: downloads go through the CloudAdapter, and the
URIs come from the environment (REF_URI, CUR_URI).
"""

import os
import runpy
import sys
from pathlib import Path

from cloudlayer.factory import get_adapter
from src import config


def main() -> int:
    adapter = get_adapter(config.load(strict=False))
    ref, cur = Path("/tmp/reference.csv"), Path("/tmp/current.csv")
    adapter.download(os.environ["REF_URI"], str(ref))
    adapter.download(os.environ["CUR_URI"], str(cur))
    sys.argv = [
        "monitoring.drift",
        "--reference", str(ref),
        "--current", str(cur),
        "--out", "/tmp/drift.json",
        "--emit",
    ]
    try:
        runpy.run_module("monitoring.drift", run_name="__main__")
    except SystemExit as exc:
        # drift.py exits 2 when a feature is above threshold. The alert is carried by the
        # emitted metric, so the job itself should only fail if the check could not run.
        code = exc.code if isinstance(exc.code, int) else 1
        print(f"drift exit code {code}")
        return 0 if code in (0, 2) else code
    return 0


if __name__ == "__main__":
    sys.exit(main())
