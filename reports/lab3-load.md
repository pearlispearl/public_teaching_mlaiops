## Task 3: Load Testing & Performance Analysis

### 1. Latency Target Specification
* **Target Metric**: p95 latency for single-item prediction (`/predict`)
* **Stated Threshold**: <= 250 ms
* **Justification**: This threshold ensures a responsive synchronous inference API experience for predictive maintenance monitoring, well below the acceptable limit for real-time alerting systems.
* **Target committed at**: [fill in: commit hash + timestamp from `git log --format='%h %ad' -- reports/lab3-load.md`]
* **Run order**: [fill in honestly: which k6 runs happened before the target was committed, if any]

---

### 2. Concurrency Performance Report
Tool: `k6` (`loadtest/k6_vertex.js`), 60 s per level, client in Bangkok, endpoint in `asia-southeast1`.
Raw output: `reports/k6-vus1.txt`, `reports/k6-vus10.txt`, `reports/k6-vus50.txt`.

| Concurrency (VUs) | Requests | Throughput (RPS) | p50 | p95 | p99 | Max | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1 VU** | 157 | 2.61 (about 4.3 after the stall, see notes) | 208.69 ms | 632.42 ms | 5.71 s | 5.86 s | 0.00% |
| **10 VUs** | 1459 | 24.22 | 407.49 ms | 609.57 ms | 772.4 ms | 1.56 s | 0.00% |
| **50 VUs** | 1506 | 24.51 | 2.02 s | 2.63 s | 2.95 s | 3.28 s | 0.00% |

* **Breaking Point**: The 200 ms p95 target was **not met at any tested level**, including 1 VU (p50 alone is 208.69 ms). No errors appeared up to 50 VUs, so the breaking point is set by latency, not failures.
* **Saturation**: Throughput stops growing at about 24 RPS. It is 24.22 at 10 VUs and 24.51 at 50 VUs, while p50 grows from 407 ms to 2.02 s (roughly in proportion to concurrency). This is queueing on a fixed-capacity service.

**Interpretation (hypothesis, to be verified with server logs):**
* Closed-loop check (Little's law): 10 / 0.410 s = 24.4 RPS and 50 / 2.02 s = 24.8 RPS, consistent with the measured throughput.
* A ceiling of about 24.4 RPS implies roughly 41 ms of serialized service time per request. The rest of the 1 VU latency (about 165 ms) would then be fixed overhead outside that bottleneck (network and platform).
* Estimated saturation knee: 24.4 RPS x 0.208 s = about 5 concurrent requests. This is an estimate, not a measurement.

**Notes on the 1 VU run:**
* Progress lines show very slow progress between about 6 s and 30 s (19 to 26 completed iterations), with the rest of the run at about 4-5 RPS. This produced p99 = 5.71 s, far above p95.
* Cause: [fill in after checking Cloud Logging for that window, and after a repeat run]

---

### 3. Variable Stress Analysis

#### A. Batch Size Comparison (`/predict/batch` vs. Single Calls)
* **Setup**: [fill in]
* **Findings**: Not yet measured.

#### B. Payload Size Impact
* **Setup**: [fill in]
* **Findings**: Not yet measured.

#### C. Instance Size Scaling
* **Setup**: Current machine type: [fill in from the deployed endpoint]. Next step up: [fill in].
* **Findings**: Not yet measured. Report the p95 change and the hourly cost change.
