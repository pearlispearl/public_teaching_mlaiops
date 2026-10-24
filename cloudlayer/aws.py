"""AWS adapter, Lab 5 Task 4 Part B: upload, download and invoke only.

SDK:  pip install -r requirements-aws.txt   (boto3; kept out of the serving image on purpose)

Scope is deliberate. The lab asks for three methods of a SECOND provider, enough to prove the
seam is real. Every other method is inherited from CloudAdapter and keeps its "not
implemented yet" behaviour, so nothing here pretends to be a full migration.

Notes from writing it:
  * BLOB_URI is s3://bucket/prefix. It is parsed here and nowhere else.
  * Credentials come from boto3's default chain (AWS_PROFILE, env vars, or an instance role).
    No key ever appears in this repo.
  * invoke() takes either a SageMaker endpoint NAME or the full https URL of a service that
    already speaks our JSON contract (for example an App Runner service running the Lab 3 image,
    which needs no change to its routes). The two behave differently, and that difference is
    the leak written up in the Task 4 report: SageMaker fixes the routes (/invocations, /ping),
    so the same image needs a shim there, while a plain HTTPS service does not.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3

from cloudlayer.base import CloudAdapter


def _split(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Expected an s3://bucket/key URI, got {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/")


class AwsAdapter(CloudAdapter):
    def _s3(self):
        return boto3.client("s3", region_name=self.cfg.region)

    def upload(self, local_path: str, key: str) -> str:
        bucket, prefix = _split(self.cfg.blob_uri)
        full_key = f"{prefix.rstrip('/')}/{key.lstrip('/')}" if prefix else key.lstrip("/")
        self._s3().upload_file(
            local_path,
            bucket,
            full_key,
            ExtraArgs={"Metadata": {k: str(v) for k, v in self.cfg.tags(5).items()}},
        )
        return f"s3://{bucket}/{full_key}"

    def download(self, uri: str, local_path: str) -> None:
        bucket, key = _split(uri)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self._s3().download_file(bucket, key, local_path)

    def invoke(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if endpoint.startswith("https://"):
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as reply:
                return json.loads(reply.read())
        runtime = boto3.client("sagemaker-runtime", region_name=self.cfg.region)
        reply = runtime.invoke_endpoint(
            EndpointName=endpoint,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload),
        )
        return json.loads(reply["Body"].read())

    def push_image(self, local_tag: str) -> str:
        """Required by the interface so the class can be instantiated. Not exercised by the
        swap check and not tested against a real registry; follows the ECR login recipe."""
        registry = self.cfg.container_registry
        host = registry.split("/")[0]
        password = subprocess.run(
            ["aws", "ecr", "get-login-password", "--region", self.cfg.region],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        subprocess.run(
            ["docker", "login", "--username", "AWS", "--password-stdin", host],
            input=password, text=True, check=True,
        )
        remote_tag = f"{registry}/{local_tag}"
        subprocess.run(["docker", "tag", local_tag, remote_tag], check=True)
        subprocess.run(["docker", "push", remote_tag], check=True)
        out = subprocess.run(
            ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", remote_tag],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()

    # Not implemented in this lab (Part B asks for three methods only):
    # submit_training / register_model (SageMaker), deploy, emit_metric
    # (CloudWatch), generate (Bedrock), teardown (resourcegroupstaggingapi).
