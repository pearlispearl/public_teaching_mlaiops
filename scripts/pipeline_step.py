"""Lab 5 — the logic of every pipeline step, in one entrypoint inside the image.

    python scripts/pipeline_step.py <ingest|validate|train|evaluate|register|deploy_staging> \
        --run-id RUN [--decision-out FILE]

Each step is a separate container with no shared disk, so steps hand data to each other
through BLOB_URI under pipeline/<run-id>/, always through the cloud adapter. A step that
fails exits non-zero, which stops everything downstream of it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config, seeds

SEED = str(seeds.DEFAULT_SEED)
TMP = Path("/tmp/pipeline")


def run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


class Step:
    def __init__(self, run_id: str) -> None:
        self.cfg = config.load()
        self.adapter = get_adapter(self.cfg)
        self.run_id = run_id
        self.raw = Path(self.cfg.raw_path)
        TMP.mkdir(parents=True, exist_ok=True)

    def uri(self, rel: str) -> str:
        return f"{self.cfg.blob_uri.rstrip('/')}/pipeline/{self.run_id}/{rel}"

    def put(self, local: Path, rel: str) -> str:
        return self.adapter.upload(str(local), f"pipeline/{self.run_id}/{rel}")

    def fetch_raw(self) -> None:
        self.raw.parent.mkdir(parents=True, exist_ok=True)
        self.adapter.download(self.uri("raw/sensors.csv"), str(self.raw))

    def ingest(self) -> None:
        self.raw.parent.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "scripts/make_dataset.py", "--seed", SEED, "--out", str(self.raw)])
        print("uploaded", self.put(self.raw, "raw/sensors.csv"))

    def validate(self) -> None:
        self.fetch_raw()
        run([sys.executable, "-m", "pytest", "-q", "tests/test_data.py"])

    def train(self) -> None:
        self.fetch_raw()
        metrics = TMP / "metrics.json"
        env = {**os.environ, "MLFLOW_TRACKING_URI": f"sqlite:///{TMP}/mlflow.db"}
        run([sys.executable, "-m", "src.train", "--seed", SEED,
             "--metrics-out", str(metrics)], env=env)
        # Same seed, same data, same hyperparameters and n_jobs=1: this is the model that
        # was just evaluated, written where the serving container expects model.joblib.
        model = TMP / "model" / "model.joblib"
        run([sys.executable, "scripts/export_model.py", "--seed", SEED, "--out", str(model)])
        self.put(model, "model/model.joblib")
        self.put(metrics, "metrics.json")

    def _metrics(self) -> dict:
        local = TMP / "metrics.json"
        self.adapter.download(self.uri("metrics.json"), str(local))
        return json.loads(local.read_text())

    def evaluate(self, decision_out: str | None) -> None:
        self._metrics()
        decision = Path(decision_out) if decision_out else TMP / "decision.txt"
        decision.parent.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "scripts/evaluation_gate.py", "--metrics",
             str(TMP / "metrics.json"), "--decision-out", str(decision)])
        print("gate decision:", decision.read_text())
        self.put(decision, "decision.txt")

    def register(self) -> None:
        metrics = self._metrics()
        lineage = {
            "git-commit": os.environ.get("GIT_COMMIT", "unknown"),
            "data-version": metrics.get("data_fingerprint", "unknown"),
            "pipeline-run": self.run_id,
            "seed": metrics.get("seed", SEED),
            "metric-val": round(metrics["val_roc_auc"], 4),
            "metric-test": round(metrics["test_roc_auc"], 4),
            "lab": 5,
        }
        # The serving image is the Lab 3 image, pinned by digest. It reads the model this
        # run just wrote, so the model and the code that loads it come from the same pins.
        serving_image = os.environ.get("SERVE_IMAGE")
        serving_env = None
        if serving_image:
            serving_env = {
                "CLOUD_PROVIDER": self.cfg.provider,
                "PROJECT_ID": self.cfg.project_id,
                "REGION": self.cfg.region,
                "BLOB_URI": self.cfg.blob_uri,
                "MODEL_BLOB_KEY": f"pipeline/{self.run_id}/model/model.joblib",
                "MODEL_REGISTRY_NAME": self.cfg.model_registry_name,
                "MODEL_VERSION": self.run_id,
                "MLFLOW_TRACKING_URI": "sqlite:////tmp/mlflow.db",
            }
        version = self.adapter.register_model(
            model_uri=self.uri("model"), name=self.cfg.model_registry_name, lineage=lineage,
            serving_image=serving_image, serving_env=serving_env)
        print("registered version", version)

    def deploy_staging(self) -> None:
        endpoint = f"{self.cfg.model_registry_name}-staging"
        instance = os.environ.get("SERVE_INSTANCE", "n1-standard-4")
        print("endpoint", self.adapter.deploy_model(
            self.cfg.model_registry_name, endpoint, instance,
            service_account=os.environ.get("SERVE_SERVICE_ACCOUNT") or None))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["ingest", "validate", "train", "evaluate",
                                     "register", "deploy_staging"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--decision-out", default=None)
    args = ap.parse_args()

    step = Step(args.run_id)
    if args.step == "evaluate":
        step.evaluate(args.decision_out)
    else:
        getattr(step, args.step)()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
