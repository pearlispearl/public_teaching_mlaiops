"""Lab 3 -- Task 4 canary deployment.

Deploys two model versions to one endpoint with a 90/10 traffic split, using the same
container image but different MODEL_BLOB_KEY per deployed model. Kept separate from
cloudlayer/gcp.py's deploy() (used by Tasks 1-3) to avoid touching graded code.
"""
from __future__ import annotations
import subprocess
from google.cloud import aiplatform
from src import config

cfg = config.load(strict=False)
aiplatform.init(project=cfg.project_id, location=cfg.region, staging_bucket=cfg.blob_uri)

tag = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
image_uri = f"asia-southeast1-docker.pkg.dev/{cfg.project_id}/itcs355/itcs355-serve:{tag}"

endpoint_name = "itcs355-canary-endpoint"

def upload_model(display_name, blob_key, version_label):
    return aiplatform.Model.upload(
        display_name=display_name,
        artifact_uri=cfg.blob_uri,
        serving_container_image_uri=image_uri,
        serving_container_predict_route="/predict",
        serving_container_health_route="/ready",
        serving_container_ports=[8080],
        serving_container_environment_variables={
            "MODEL_BLOB_KEY": blob_key,
            "MODEL_VERSION": version_label,
            "BLOB_URI": cfg.blob_uri,
            "CLOUD_PROVIDER": "gcp",
            "PROJECT_ID": cfg.project_id,
        },
        labels=cfg.tags(3),
    )

model_v1 = upload_model("canary-v1-good", "models/canary/v1/model.joblib", "v1-good")
model_v2 = upload_model("canary-v2-worse", "models/canary/v2/model.joblib", "v2-worse")

endpoints = aiplatform.Endpoint.list(filter="display_name=\"" + endpoint_name + "\"")
endpoint = endpoints[0] if endpoints else aiplatform.Endpoint.create(
    display_name=endpoint_name, labels=cfg.tags(3)
)

model_v1.deploy(
    endpoint=endpoint, deployed_model_display_name="v1-good",
    machine_type="n1-standard-4", min_replica_count=1, max_replica_count=1,
    traffic_percentage=100,
)
print("v1 deployed. Endpoint:", endpoint.resource_name)

model_v2.deploy(
    endpoint=endpoint, deployed_model_display_name="v2-worse",
    machine_type="n1-standard-4", min_replica_count=1, max_replica_count=1,
    traffic_percentage=10,
)
print("v2 deployed at 10% traffic. Endpoint:", endpoint.resource_name)
print("Deployed models:", endpoint.list_models())
