"""Lab 5 Task 1 — compile the neutral DAG, submit it to Vertex AI Pipelines, wait.

    python scripts/run_pipeline.py                 # compile only (no cloud calls)
    python scripts/run_pipeline.py --submit --wait

Needs `pip install -r requirements-pipeline.txt`. Run it from a machine that is logged in
to the cloud; the run itself executes in the cloud under IDENTITY_REF.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.pipelines import compile_for, load_spec
from src import config


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    cfg = config.load()
    spec = load_spec()
    compiled = compile_for(cfg.provider, spec)
    print(f"compiled {compiled}")
    if not args.submit:
        return 0

    from google.cloud import aiplatform  # provider SDK: allowed here, not in src/

    aiplatform.init(project=cfg.project_id, location=cfg.region)
    job = aiplatform.PipelineJob(
        display_name=spec["name"],
        template_path=str(compiled),
        pipeline_root=f"{cfg.blob_uri.rstrip('/')}/pipeline-root",
        enable_caching=False,
        labels=cfg.tags(5),
    )
    job.submit(service_account=cfg.identity_ref or None)
    print(f"submitted {job.resource_name}")
    if args.wait:
        while True:
            state = job.state.name
            print(time.strftime("%H:%M:%S"), state, flush=True)
            if state in ("PIPELINE_STATE_SUCCEEDED", "PIPELINE_STATE_FAILED",
                         "PIPELINE_STATE_CANCELLED"):
                return 0 if state == "PIPELINE_STATE_SUCCEEDED" else 1
            time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
