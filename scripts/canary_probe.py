"""Lab 3 -- Task 4: continuous probing to detect canary degradation from metrics alone.

Sends steady traffic to the endpoint (which is Vertex-side split 90/10 between v1/v2),
and logs each response's model_version + a proxy metric (here: prediction probability,
since both models score the same fixed input -- a shift in the score distribution for a
given version is what we'd watch for in a real dashboard, alongside error rate).
"""
from __future__ import annotations
import sys
import time
import subprocess
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

ENDPOINT_ID = "6311031816690073600"
PROJECT_ID = "itcs355-6688015"
URL = f"https://asia-southeast1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/asia-southeast1/endpoints/{ENDPOINT_ID}:rawPredict"

PAYLOAD = {
    "temp_c": 75.0, "vibration_mm_s": 12.5, "pressure_kpa": 250.0,
    "hours_since_service": 120.0, "load_pct": 65.0, "ambient_humidity": 45.0,
}


def get_token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()


def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    log_path = Path("reports/canary-probe-log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    with open(log_path, "a") as f:
        for i in range(n):
            t0 = time.time()
            resp = requests.post(URL, json=PAYLOAD, headers=headers, timeout=10)
            latency_ms = (time.time() - t0) * 1000
            record = {
                "i": i,
                "ts": time.time(),
                "status": resp.status_code,
                "latency_ms": round(latency_ms, 2),
            }
            if resp.status_code == 200:
                body = resp.json()
                record["model_version"] = body.get("model_version")
                record["probability"] = body.get("probability")
            else:
                record["error"] = resp.text[:200]
            f.write(json.dumps(record) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"[{i}/{n}] status={record['status']} version={record.get('model_version')} prob={record.get('probability')}")


if __name__ == "__main__":
    main()
