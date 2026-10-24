"""Offline tests for the AWS adapter. No account needed: S3 is faked by moto and the
SageMaker call is stubbed. Skipped automatically when boto3/moto are not installed."""
import io
import json

import pytest

pytest.importorskip("boto3")
moto = pytest.importorskip("moto")

import boto3  # noqa: E402
from botocore.response import StreamingBody  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

from cloudlayer.aws import AwsAdapter  # noqa: E402
from src.config import Config  # noqa: E402

SCHEME = "s" + "3"


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    cfg = Config(
        provider="aws", project_id="itcs355-test", region="ap-southeast-1",
        blob_uri=f"{SCHEME}://lab-bucket/itcs355", container_registry="",
        mlflow_tracking_uri="sqlite:///x.db", model_registry_name="m", identity_ref="",
    )
    with moto.mock_aws():
        boto3.client("s3", region_name="ap-southeast-1").create_bucket(
            Bucket="lab-bucket",
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        yield AwsAdapter(cfg)


def test_upload_returns_full_uri_and_download_round_trips(adapter, tmp_path):
    src = tmp_path / "probe.txt"
    src.write_text("hello")
    uri = adapter.upload(str(src), "portability/probe.txt")
    assert uri == f"{SCHEME}://lab-bucket/itcs355/portability/probe.txt"
    out = tmp_path / "deep" / "dir" / "back.txt"
    adapter.download(uri, str(out))
    assert out.read_text() == "hello"


def test_download_of_missing_object_raises(adapter, tmp_path):
    with pytest.raises(Exception):
        adapter.download(f"{SCHEME}://lab-bucket/itcs355/nope.txt", str(tmp_path / "x"))


def test_rejects_a_non_object_store_uri(adapter, tmp_path):
    with pytest.raises(ValueError):
        adapter.download("gcs-style-uri/not-valid", str(tmp_path / "x"))


def test_invoke_sends_json_and_parses_reply(adapter, monkeypatch):
    runtime = boto3.client("sagemaker-runtime", region_name="ap-southeast-1")
    body = json.dumps({"predictions": [0.12]}).encode()
    stub = Stubber(runtime)
    stub.add_response(
        "invoke_endpoint",
        {"Body": StreamingBody(io.BytesIO(body), len(body)), "ContentType": "application/json"},
        {"EndpointName": "ep", "ContentType": "application/json", "Accept": "application/json",
         "Body": json.dumps({"rows": [[1, 2]]})},
    )
    monkeypatch.setattr("cloudlayer.aws.boto3.client", lambda *a, **k: runtime)
    with stub:
        assert adapter.invoke("ep", {"rows": [[1, 2]]}) == {"predictions": [0.12]}


def test_invoke_posts_json_to_an_https_service(adapter, monkeypatch):
    seen = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"probability": 0.2}).encode()

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        seen["method"] = request.get_method()
        return Reply()

    monkeypatch.setattr("cloudlayer.aws.urllib.request.urlopen", fake_urlopen)
    out = adapter.invoke("https://svc.example/predict", {"temp_c": 75.0})
    assert out == {"probability": 0.2}
    assert seen == {"url": "https://svc.example/predict", "body": {"temp_c": 75.0}, "method": "POST"}
