"""Lab 5 Task 3 - put the weekly retrain on a real schedule (Vertex AI), created PAUSED.

    IMAGE_TAG=<pushed tag> python scripts/create_schedule.py            # create + pause
    python scripts/create_schedule.py --delete                          # remove it

The cron comes from `schedule:` in pipeline/pipeline.yaml. It is created paused with a run
limit of 1, so the resource exists for inspection (and teardown) without starting a run on
its own while the lab is being graded. `make teardown` deletes it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.pipelines import compile_for, load_spec
from src import config

TIMEZONE = "Asia/Bangkok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()

    cfg = config.load()
    spec = load_spec()
    name = f"{spec['name']}-weekly"

    from google.cloud import aiplatform  # provider SDK: allowed here, not in src/

    aiplatform.init(project=cfg.project_id, location=cfg.region)

    if args.delete:
        for s in aiplatform.PipelineJobSchedule.list():
            if s.display_name == name:
                s.delete()
                print(f"deleted {s.resource_name}")
        return 0

    compiled = compile_for(cfg.provider, spec)
    job = aiplatform.PipelineJob(
        display_name=spec["name"],
        template_path=str(compiled),
        pipeline_root=f"{cfg.blob_uri.rstrip('/')}/pipeline-root",
        enable_caching=False,
        labels=cfg.tags(5),
    )
    schedule = aiplatform.PipelineJobSchedule(pipeline_job=job, display_name=name)
    schedule.create(
        cron=f"CRON_TZ={TIMEZONE} {spec['schedule']}",
        max_run_count=1,
        service_account=cfg.identity_ref or None,
    )
    schedule.pause()
    print(f"created {schedule.resource_name}")
    print(f"cron    CRON_TZ={TIMEZONE} {spec['schedule']}")
    print(f"state   {schedule.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
