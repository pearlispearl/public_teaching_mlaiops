"""The register and deploy steps must hand the serving image and identity to the adapter."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pipeline_step as ps  # noqa: E402


class FakeAdapter:
    def __init__(self):
        self.registered = {}
        self.deployed = {}

    def download(self, uri, local_path):
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_text(json.dumps(
            {"seed": 1, "data_fingerprint": "abc", "val_roc_auc": 0.84, "test_roc_auc": 0.83}))

    def register_model(self, **kwargs):
        self.registered = kwargs
        return "1"

    def deploy_model(self, name, endpoint, instance, service_account=None):
        self.deployed = {"endpoint": endpoint, "service_account": service_account}
        return "endpoint-resource"


@pytest.fixture
def step(monkeypatch, tmp_path):
    for key, value in {
        "CLOUD_PROVIDER": "local", "PROJECT_ID": "p", "REGION": "r", "BLOB_URI": "mem://b/x",
        "CONTAINER_REGISTRY": "reg", "MLFLOW_TRACKING_URI": "sqlite:///x.db",
        "MODEL_REGISTRY_NAME": "m", "IDENTITY_REF": "i",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(ps, "TMP", tmp_path)
    fake = FakeAdapter()
    monkeypatch.setattr(ps, "get_adapter", lambda cfg: fake)
    return ps.Step("run-1"), fake


def test_register_passes_the_serving_image_and_this_runs_model_key(step, monkeypatch):
    s, fake = step
    monkeypatch.setenv("SERVE_IMAGE", "reg/serve@sha256:abc")
    s.register()
    assert fake.registered["serving_image"] == "reg/serve@sha256:abc"
    env = fake.registered["serving_env"]
    assert env["MODEL_BLOB_KEY"] == "pipeline/run-1/model/model.joblib"
    assert env["BLOB_URI"] == "mem://b/x"


def test_register_without_a_serving_image_keeps_the_default_container(step, monkeypatch):
    s, fake = step
    monkeypatch.delenv("SERVE_IMAGE", raising=False)
    s.register()
    assert fake.registered["serving_image"] is None
    assert fake.registered["serving_env"] is None


def test_deploy_runs_the_endpoint_as_the_serving_identity(step, monkeypatch):
    s, fake = step
    monkeypatch.setenv("SERVE_SERVICE_ACCOUNT", "serve@example")
    s.deploy_staging()
    assert fake.deployed["service_account"] == "serve@example"
