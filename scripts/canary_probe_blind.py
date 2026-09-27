"""Lab 3 -- Task 4: BLIND canary probing.

Detection must happen from metrics alone, without looking at which version is which.
This script logs model_version to the raw file (needed later as evidence of what
actually happened), but the live console output during monitoring shows ONLY
status/latency/probability -- never the version label. The operator (you) should
decide "something looks wrong" purely from the printed probability clusters, before
ever opening the log file to check which version produced them.
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
    log_path = Path("reports/canary-probe-blind-log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seen_probs = set()

    with open(log_path, "a") as f:
        for i in range(n):
            t0 = time.time()
            resp = requests.post(URL, json=PAYLOAD, headers=headers, timeout=10)
            latency_ms = (time.time() - t0) * 1000
            record = {"i": i, "ts": time.time(), "status": resp.status_code, "latency_ms": round(latency_ms, 2)}

            if resp.status_code == 200:
                body = resp.json()
                # Recorded for later evidence -- NOT printed to console now.
                record["model_version"] = body.get("model_version")
                record["probability"] = body.get("probability")
            else:
                record["error"] = resp.text[:200]

            f.write(json.dumps(record) + "\n")
            f.flush()

            # BLIND monitoring output: no version label, just what an aggregate dashboard
            # would show -- status, latency, and the raw score.
            prob = record.get("probability")
            if prob is not None:
                prob_r = round(prob, 4)
                is_new_cluster = prob_r not in seen_probs
                seen_probs.add(prob_r)
                flag = "  <-- NEW DISTINCT VALUE SEEN" if is_new_cluster and len(seen_probs) > 1 else ""
                print(f"[{i}/{n}] status={record['status']} latency={record['latency_ms']}ms prob={prob_r}{flag}")
            else:
                print(f"[{i}/{n}] status={record['status']} latency={record['latency_ms']}ms ERROR={record.get('error')}")


if __name__ == "__main__":
    main()
