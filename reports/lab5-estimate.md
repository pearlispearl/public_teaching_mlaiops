# Lab 5 — Cost estimate (made BEFORE running anything)

Committed before Task 1. Prices come from my own Lab 1-4 billing export
(2026-09-01 to 2026-10-31, total 357.49 THB), not from a price list.

## What the billing export taught me

| Line | THB | Reading |
|---|---|---|
| Vertex online prediction, N1 core + RAM | 343.65 | One `n1-standard-4` endpoint (154.74 core-hours / 4 = ~38.7 h) = 96% of all spend |
| Artifact Registry storage (2.5 GiB) | 5.24 | Small but recurring |
| Cloud Run (services + job) | ~3.8 | Scale-to-zero serving is almost free |
| Spot compute | ~3.3 | |
| Vertex training / pipelines | ~1.5 | All Lab 2 jobs together |

Derived rates: a provisioned `n1-standard-4` endpoint costs about 8.9 THB/hour
(1.48 THB/core-hour x 4 + 0.197 THB/GiB-hour x 15), which is about 213 THB per day.

Budget: 800 THB for the term. Spent so far 357.49 THB. Remaining 442.51 THB.

## Plan and assumptions

- **Before:** one Vertex endpoint (`n1-standard-4`, 1 replica, cannot scale to zero) is deployed
  for a bounded measurement window of at most 4 hours: p95 latency and THB per 1,000
  predictions are measured on it.
- **After (the Task 5 optimisation):** the same serving image moves to Cloud Run
  (scale to zero) and the same measurements are repeated.
- The endpoint is deleted the same day it is created. Hard stop: 4 hours after deploy.
- About 5 pipeline runs in total (2 failed, 1 gate-FAIL demonstration, 2 clean).
- LLM step uses a small managed model; about 150 calls over the lab.
- Everything is created with `course=itcs355, lab=5` from the start.

## Estimate by component

| Component | THB | Basis |
|---|---|---|
| Training (pipeline steps) | 8 | 5 runs x ~1.5 THB, the per-run cost seen in Lab 2 |
| Pipeline (run management fee) | 5 | 5 runs x ~1 THB; to verify on the Vertex pricing page |
| Storage (registry + bucket) | 3 | ~2.6 THB/month registry + bucket under 0.1 THB |
| Serving, before (Vertex endpoint) | 36 | 4 h x 8.9 THB/h, derived from my billing export |
| Serving, after (Cloud Run staging) | 3 | Lab 3/4 Cloud Run total was ~3.8 THB |
| LLM tokens | 5 | 150 calls, ~500 in / ~100 out tokens; to verify against llmcost.py rates |
| Monitoring / logging | 0 | Under free tier in Lab 4 |
| **Subtotal** | **60** | |
| Contingency (+50% on everything except the endpoint) | 12 | failed runs and reruns |
| **Estimate** | **72 THB** | |

## Risk that would break this estimate

The endpoint is the whole risk. Every extra hour is 8.9 THB, and a forgotten endpoint is
about 213 THB per day. Teardown is verified in the console the same day, and the billing
export lags by a day or more, so the actual figure is read from billing only after that.
