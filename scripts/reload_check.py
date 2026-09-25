"""Lab 2 — prove the registered model can be reloaded by version, from the registry.

    python scripts/reload_check.py --name itcs355-<studentid> --version 3

This is the lab's quiet test. Models that cannot be reloaded six months later are the
commonest form of dead work in industry, and the cause is nearly always a serialization
assumption: a custom class that no longer exists, a library version that moved, a
preprocessing step that only ever lived in a notebook.

Loading from a local file instead of the registry defeats the purpose and is checked.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
from google.cloud import aiplatform

from src import config, data
from cloudlayer.factory import get_adapter


def _load_from_registry(cfg, name: str, version: str):
    """Pull the model artifact from Vertex AI Model Registry by name + version.

    Task 4 registers via adapter.register_model() -> aiplatform.Model.upload(),
    which lands in Vertex AI's own registry -- not MLflow's. This must match.
    """
    aiplatform.init(project=cfg.project_id, location=cfg.region)

    candidates = aiplatform.Model.list(filter=f'display_name="{name}"')
    if not candidates:
        raise RuntimeError(f"No model with display_name={name!r} found in Vertex AI Model Registry")

    match = next((m for m in candidates if m.version_id == str(version)), None)
    if match is None:
        available = [m.version_id for m in candidates]
        raise RuntimeError(
            f"No version={version!r} for {name!r}. Available versions: {available}"
        )

    adapter = get_adapter(cfg)
    with tempfile.TemporaryDirectory() as tmp:
        local_path = str(Path(tmp) / "model.joblib")
        artifact_key = f"{match.gca_resource.artifact_uri.rstrip('/')}/model.joblib"
        adapter.download(artifact_key, local_path)
        return joblib.load(local_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="registered model name")
    ap.add_argument("--version", required=True)
    ap.add_argument("--rows", type=int, default=5)
    args = ap.parse_args()

    cfg = config.load(strict=False)

    print(f"loading {args.name}:{args.version} from Vertex AI Model Registry")
    model = _load_from_registry(cfg, args.name, args.version)

    df = data.load_raw(cfg.raw_path)
    _, _, test_df = data.split(df, seed=20260101)
    sample = test_df.head(args.rows)
    preds = model.predict_proba(sample[data.FEATURES])[:, 1]

    for rid, p in zip(sample[data.ID], preds):
        print(f"  reading {rid}: p(failure)={p:.4f}")
    print("\nPASS  model reloaded from the registry and scored rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())