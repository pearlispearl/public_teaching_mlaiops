## Task 3: Load Testing & Performance Analysis

### 1. Latency Target Specification
* **Target Metric**: p95 Latency for single-item prediction (`/predict`)
* **Stated Threshold**: $\le 200\text{ ms}$
* **Justification**: This threshold ensures a responsive synchronous inference API experience for predictive maintenance monitoring, well below the acceptable limit for real-time alerting systems.

---

### 2. Concurrency Performance Report
Tested at three concurrency levels using `k6` load testing.

| Concurrency (VUs) | Throughput (RPS) | p50 Latency | p95 Latency | p99 Latency | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1 VU** | *[Fill in]* | *[Fill in]* | *[Fill in]* | *[Fill in]* | *[Fill in]* |
| **10 VUs** | *[Fill in]* | *[Fill in]* | *[Fill in]* | *[Fill in]* | *[Fill in]* |
| **50 VUs** | *[Fill in]* | *[Fill in]* | *[Fill in]* | *[Fill in]* | *[Fill in]* |

* **Breaking Point**: Concurrency reached **[Fill in VUs]**, where p95 latency crossed the $200\text{ ms}$ target / error rates began to appear.

---

### 3. Variable Stress Analysis

#### A. Batch Size Comparison (`/predict/batch` vs. Single Calls)
* **Setup**: Compared 1 batch request with 100 rows against 100 sequential single-item requests to `/predict`.
* **Findings**: Batching improved throughput by **[Fill in]%** and reduced overall latency by **[Fill in] ms** due to minimized network overhead and vectorized DataFrame processing in Pandas.

#### B. Payload Size Impact
* **Setup**: Inflated request payloads with redundant feature fields.
* **Findings**: Serialization and deserialization overhead began to dominate and degrade latency significantly once the payload size exceeded **[Fill in] KB**.

#### C. Instance Size Scaling
* **Setup**: Upgraded instance size from `n1-standard-4` to **[Fill in higher tier, e.g., n1-standard-8]**.
* **Findings**: 
  * **Latency Change**: p95 latency decreased by **[Fill in]%**.
  * **Cost Change**: Estimated infrastructure cost increased by **[Fill in]%** per hour.