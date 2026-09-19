"""Register the chosen trial's model to Vertex AI with full lineage."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
from src import config
from cloudlayer.factory import get_adapter

RUN_ID       = "53a0b9db97604d3d84fe777910ba0853"
TRAINING_JOB = "projects/116618257996/locations/asia-southeast1/customJobs/5282624231492812800"
IMAGE_DIGEST = "asia-southeast1-docker.pkg.dev/itcs355-6688015/itcs355/itcs355-lab1@sha256:9d72e11d52d5a911ab93d966987c8fc006ed9be025616dfdf5c10cc54f6b4e7a"
cfg     = config.load()
adapter = get_adapter(cfg)

mlflow.set_tracking_uri("sqlite:///reports/mlflow.db")
run     = mlflow.get_run(RUN_ID)

lineage = {
    "git-commit":       run.data.tags["git_commit"],
    "data-version":     run.data.tags["data_fingerprint"],
    "mlflow-run-id":    RUN_ID[:20],
    "training-job-id":  TRAINING_JOB.split("/")[-1],
    "image-digest":     IMAGE_DIGEST.split("@sha256:")[-1][:20],
    "seed":             run.data.params.get("seed", "20260101"),
    "metric-val":       str(round(run.data.metrics["val_roc_auc"], 4)),
    "metric-test":      str(round(run.data.metrics["test_roc_auc"], 4)),
}

artifact_gcs = f"{cfg.blob_uri.rstrip('/')}/models/trial-05"

version = adapter.register_model(
    model_uri=artifact_gcs,
    name="itcs355-lab2",
    lineage=lineage,
)
print(f"Registered version: {version}")
