"""GCP adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install google-cloud-storage google-cloud-aiplatform
Docs: storage.Client for GCS; Artifact Registry push goes through `docker push` after
      `gcloud auth configure-docker <region>-docker.pkg.dev`.

Hints for Lab 1:
  * BLOB_URI looks like gs://bucket/prefix — parse it here, never in src/.
  * Artifact Registry paths are region-scoped:
        <region>-docker.pkg.dev/<project>/<repo>/<image>
    A common first failure is pushing to gcr.io out of habit; it is a different service.
  * push_image must return the digest reference, not the tag.
  * GCP calls them labels, not tags, and they must be lowercase with no spaces.
    cfg.tags(1) already satisfies that constraint — do not "improve" the values.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from google.cloud import storage
from cloudlayer.base import CloudAdapter

class GcpAdapter(CloudAdapter):
    def upload(self, local_path: str, key: str) -> str:
        # Parse bucket name & object key from config/BLOB_URI
        bucket_uri = self.cfg.bucket_name if hasattr(self.cfg, "bucket_name") else self.cfg.bucket
        if bucket_uri.startswith("gs://"):
            bucket_name = urlparse(bucket_uri).netloc
        else:
            bucket_name = bucket_uri.split("/")[0]

        client = storage.Client(project=getattr(self.cfg, "project_id", None))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        blob.upload_from_filename(local_path)

        return f"gs://{bucket_name}/{key}"

    def download(self, uri: str, local_path: str) -> None:
        parsed = urlparse(uri)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip('/')

        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        client = storage.Client(project=getattr(self.cfg, "project_id", None))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)

    def push_image(self, local_tag: str) -> str:
        region = getattr(self.cfg, "region", "asia-southeast1")
        project_id = getattr(self.cfg, "project_id", "itcs355-6688015")
        repo_name = getattr(self.cfg, "repository", "itcs355")

        registry = f"{region}-docker.pkg.dev"
        remote_tag = f"{registry}/{project_id}/{repo_name}/{local_tag}"

        # 1. Authenticate Docker with Artifact Registry
        subprocess.run(["gcloud", "auth", "configure-docker", registry, "--quiet"], check=True)

        # 2. Tag & Push
        subprocess.run(["docker", "tag", local_tag, remote_tag], check=True)
        subprocess.run(["docker", "push", remote_tag], check=True)

        # 3. Extract & Return Digest (repo@sha256:...) instead of tag
        result = subprocess.run(
            ["docker", "inspect", "--format='{{index .RepoDigests 0}}'", remote_tag],
            capture_output=True, text=True, check=True
        )
        digest_ref = result.stdout.strip().strip("'\"")

        return digest_ref

    # submit_training / register_model  -> Lab 2 (Vertex custom training + Model Registry)
    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)
    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)
