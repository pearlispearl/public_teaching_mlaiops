"""Register the chosen trial's model to Vertex AI with full lineage."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
from src import config
from cloudlayer.factory import get_adapter

RUN_ID       = "ba3ca2788ed742c089c4cd81b54e593f"
TRAINING_JOB = "projects/116618257996/locations/asia-southeast1/customJobs/1449779473623810048"
IMAGE_DIGEST = "asia-southeast1-docker.pkg.dev/itcs355-6688015/itcs355/itcs355-lab1@sha256:95fc2b006f631f60b2414c3666ba1cd8de97e098bc9904f8e26c45aa02614392"

cfg     = config.load()
adapter = get_adapter(cfg)

mlflow.set_tracking_uri("sqlite:///mlflow.db")
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

artifact_gcs = f"{cfg.blob_uri.rstrip('/')}/models/lab2-chosen"

version = adapter.register_model(
    model_uri=artifact_gcs,
    name="itcs355-lab2",
    lineage=lineage,
)
print(f"Registered version: {version}")
