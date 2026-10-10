"""Scheduled drift check: fetch reference + current from GCS, run monitoring.drift --emit."""

import os
import runpy
import sys
from pathlib import Path

from google.cloud import storage


def fetch(uri: str, dest: Path) -> None:
    bucket, _, blob = uri.removeprefix("gs://").partition("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    storage.Client().bucket(bucket).blob(blob).download_to_filename(str(dest))


def main() -> None:
    ref, cur = Path("/tmp/reference.csv"), Path("/tmp/current.csv")
    fetch(os.environ["REF_URI"], ref)
    fetch(os.environ["CUR_URI"], cur)
    sys.argv = [
        "monitoring.drift",
        "--reference", str(ref),
        "--current", str(cur),
        "--out", "/tmp/drift.json",
        "--emit",
    ]
    runpy.run_module("monitoring.drift", run_name="__main__")


if __name__ == "__main__":
    main()
