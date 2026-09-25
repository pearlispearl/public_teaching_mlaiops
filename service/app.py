"""Lab 3 — inference service.

Provider-neutral by construction: the model arrives through the adapter, and the same
container image deploys to SageMaker, Azure ML, or Vertex AI. Route paths differ per
platform; that difference belongs in cloudlayer/, never here.

Run locally:  uvicorn service.app:app --port 8080
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from cloudlayer.factory import get_adapter
from service.schemas import BatchRequest, BatchResponse, PredictRequest, PredictResponse
from src import config
from src.data import FEATURES

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
)
log = logging.getLogger("service")

STATE: dict[str, Any] = {"model": None, "version": os.environ.get("MODEL_VERSION", "unknown")}


def _load_model():
    """Load once, at startup. Never per request."""
    # 1) Explicit local path (make serve / local dev)
    explicit = os.environ.get("MODEL_PATH")
    if explicit:
        return joblib.load(explicit)

    # 2) Cloud: pull the joblib straight from blob storage
    blob_uri = os.environ.get("BLOB_URI", "").rstrip("/")
    model_key = os.environ.get("MODEL_BLOB_KEY", "models/serving/model.joblib")
    if blob_uri:
        local_path = Path("/tmp/model.joblib")
        try:
            cfg = config.load(strict=False)
            adapter = get_adapter(cfg)
            adapter.download(f"{blob_uri}/{model_key}", str(local_path))
            log.info("Downloaded model from %s/%s", blob_uri, model_key)
        except Exception as exc:
            log.exception("Failed to download model")
            raise RuntimeError(f"Cannot fetch model {model_key}") from exc
        return joblib.load(local_path)

    # 3) Fallback: file baked into the image
    base_dir = Path(__file__).resolve().parent.parent
    for path in (base_dir / "reports" / "model.joblib", Path("/app/reports/model.joblib")):
        if path.exists():
            return joblib.load(path)
    raise RuntimeError("Model file not found locally and BLOB_URI is not set")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        STATE["model"] = _load_model()
        log.info(
            "model loaded successfully: registry_name=%s, version=%s",
            os.environ.get("MODEL_REGISTRY_NAME"),
            STATE["version"],
        )
    except Exception:  # readiness stays false; liveness still passes
        STATE["model"] = None
        log.exception(
            "model load failed: registry_name=%s, version=%s",
            os.environ.get("MODEL_REGISTRY_NAME"),
            STATE["version"],
        )
    yield
    STATE["model"] = None


app = FastAPI(title="ITCS355 inference", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - started) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-model-version"] = str(STATE["version"])
    log.info(
        '{"request_id":"%s","path":"%s","status":%d,"latency_ms":%.2f,"model_version":"%s"}',
        request_id, request.url.path, response.status_code, latency_ms, STATE["version"],
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness. The process is up. Says nothing about whether it can serve."""
    return {"status": "alive"}


@app.get("/ready")
def ready():
    """Readiness. The model is loaded and can score.

    These two are genuinely different, and confusing them causes a specific production
    failure: traffic routed to a container whose model has not finished loading. All three
    providers distinguish them, and Quiz 3 asks about it.
    """
    if STATE["model"] is None:
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "model not loaded"})
    return {"status": "ready", "model_version": STATE["version"]}


def _score(rows: list[dict]) -> list[float]:
    if STATE["model"] is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    frame = pd.DataFrame(rows)[FEATURES]
    return [float(p) for p in STATE["model"].predict_proba(frame)[:, 1]]


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    score = _score([payload.model_dump()])[0]
    return PredictResponse(probability=score, model_version=str(STATE["version"]))


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(payload: BatchRequest) -> BatchResponse:
    scores = _score([row.model_dump() for row in payload.rows])
    return BatchResponse(probabilities=scores, model_version=str(STATE["version"]))
