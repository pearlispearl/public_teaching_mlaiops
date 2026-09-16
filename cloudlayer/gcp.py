"""GCP adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install google-cloud-storage google-cloud-aiplatform
Docs: storage.Client for GCS; Artifact Registry push goes through `docker push` after
      `gcloud auth configure-docker <region>-docker.pkg.dev`.

Hints for Lab 1:
  * BLOB_URI looks like gs://bucket/prefix -- parse it here, never in src/.
  * Artifact Registry paths are region-scoped:
        <region>-docker.pkg.dev/<project>/<repo>/<image>
    A common first failure is pushing to gcr.io out of habit; it is a different service.
  * push_image must return the digest reference, not the tag.
  * GCP calls them labels, not tags, and they must be lowercase with no spaces.
    cfg.tags(1) already satisfies that constraint -- do not 'improve' the values.

Lab 2 notes:
  * submit_training() runs the Lab 1 image as a Vertex AI CustomJob. The job's
    run-time identity (service_account=) is deliberately different from your
    submit-time identity (whatever gcloud is authenticated as) -- expect a
    permissions failure on your first submission; that is the point of the lab.
  * wait_training() blocks until the job finishes and reports state/error, not
    metrics -- metrics live in mlflow, which the container writes to independently.
"""
from __future__ import annotations
import time
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from google.cloud import storage, aiplatform
from cloudlayer.base import CloudAdapter


class GcpAdapter(CloudAdapter):
    def upload(self, local_path: str, key: str) -> str:
        bucket_uri = self.cfg.blob_uri
        parsed = urlparse(bucket_uri)
        bucket_name = parsed.netloc

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        blob.upload_from_filename(local_path)

        return f"gs://{bucket_name}/{key}"

    def download(self, uri: str, local_path: str) -> None:
        parsed = urlparse(uri)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip('/')

        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)

    def push_image(self, local_tag: str) -> str:
        region = self.cfg.region
        registry, project_id, repo_name = self.cfg.container_registry.split("/")
        remote_tag = f"{registry}/{project_id}/{repo_name}/{local_tag}"

        subprocess.run(["gcloud", "auth", "configure-docker", registry, "--quiet"], check=True)
        subprocess.run(["docker", "tag", local_tag, remote_tag], check=True)
        subprocess.run(["docker", "push", remote_tag], check=True)

        result = subprocess.run(
            ["docker", "inspect", "--format='{{index .RepoDigests 0}}'", remote_tag],
            capture_output=True, text=True, check=True,
        )
        digest_ref = result.stdout.strip().strip("'\"")

        return digest_ref

    # --- Lab 2 -----------------------------------------------------------------

    def submit_training(self, image_uri: str, args: dict[str, Any]) -> str:
        """Submit `image_uri` as a Vertex AI custom job, running with `args` as CLI flags.

        Runs under self.cfg.identity_ref (a service account, not the identity that
        submitted the job) -- that split is deliberate; see module docstring.
        """
        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=self.cfg.blob_uri,
        )

        cli_args: list[str] = []
        for k, v in args.items():
            cli_args += [f"--{k.replace('_', '-')}", str(v)]

        machine_type = args.get("instance", "n1-standard-4")

        # ส่ง environment variables ที่ container ต้องใช้เข้าไปด้วย
        env_vars = [
            {"name": "BLOB_URI", "value": self.cfg.blob_uri},
            {"name": "PROJECT_ID", "value": self.cfg.project_id},
            {"name": "MLFLOW_TRACKING_URI", "value": self.cfg.mlflow_tracking_uri},
            {"name": "PROVIDER", "value": "gcp"},
            {"name": "IDENTITY_REF", "value": self.cfg.identity_ref},
            {"name": "CONTAINER_REGISTRY", "value": self.cfg.container_registry},
        ]

        job = aiplatform.CustomJob(
            display_name=f"itcs355-lab2-{self.cfg.tags(2)['student']}",
            worker_pool_specs=[{
                "machine_spec": {"machine_type": machine_type},
                "replica_count": 1,
                "container_spec": {
                    "image_uri": image_uri, 
                    "args": cli_args,
                    "env": env_vars,
                },
            }],
            labels=self.cfg.tags(2),
        )

        job.submit(service_account=self.cfg.identity_ref)
        return job.resource_name
    
    def wait_training(self, job_id: str) -> dict[str, Any]:
        """Block until the job reaches a terminal state, polling manually since
        a job fetched via .get() (rather than the object that called .submit())
        does not reliably block on .wait() alone.
        """
        terminal_states = {
            aiplatform.gapic.JobState.JOB_STATE_SUCCEEDED,
            aiplatform.gapic.JobState.JOB_STATE_FAILED,
            aiplatform.gapic.JobState.JOB_STATE_CANCELLED,
            aiplatform.gapic.JobState.JOB_STATE_EXPIRED,
        }

        job = aiplatform.CustomJob.get(job_id)
        while job.state not in terminal_states:
            time.sleep(15)
            job = aiplatform.CustomJob.get(job_id)  # re-fetch for updated state

        result: dict[str, Any] = {"job_id": job_id, "state": str(job.state)}
        if job.state != aiplatform.gapic.JobState.JOB_STATE_SUCCEEDED:
            result["error"] = str(job.error) if job.error else "unknown failure"
        return result

    # register_model                    -> Lab 2 (Vertex Model Registry)
    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)
    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)