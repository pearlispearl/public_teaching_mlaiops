# Lab 5: pipelines, permissions, portability and cost

Lab 4 write-up (tests, CI/CD, dashboard, drift) is in [README_Lab4.md](README_Lab4.md).
Project `itcs355-6688015`, region `asia-southeast1`. Evidence files are in `reports/`.

## Task 1: Pipeline with a real gate

The training pipeline (`pipeline/pipeline.yaml`, compiled to Vertex AI Pipelines) runs end to end, and its evaluation
gate (`scripts/evaluation_gate.py`) really decides whether a model is registered and deployed to staging.

* Gate rules: AUC at least 0.80 absolute, and it must beat the registered model by a margin larger than noise
  (0.005 when the data is the same, 0.033 when it is not).
* Run that registered and deployed a model: all steps green (`reports/lab5-task1-pipeline-green.png`).
* Run that the gate stopped: same data, so the new model is not better. The log says
  `GATE FAIL improvement +0.0000 within noise (same data, required +0.0050); not registering`, and the later steps are
  skipped (`reports/lab5-task1-gate-skip.png`, `reports/lab5-gate-pipeline-fail.txt`).
* Endpoint check: `reports/lab5-endpoint-describe.yaml`; load test against the deployed endpoint:
  `reports/lab5-k6-vertex-vus5.txt`, `reports/lab5-k6-vertex-vus10.txt`.

## Task 2: Least privilege

Identities, what each may do, the permission I removed on purpose and what broke, and the clean-up: see
[reports/lab5-iam.md](reports/lab5-iam.md). Evidence: `reports/lab5-task2-iam-break.png`, `reports/lab5-iam-break.txt`.
The AWS identities from Task 4 are in the same file.

## Task 3: Scheduled retraining

The pipeline is scheduled in `pipeline/pipeline.yaml` as `schedule: "0 2 * * 0"` (Sunday 02:00, Asia/Bangkok). The
reasoning follows; the same text is in [reports/lab5-retrain.md](reports/lab5-retrain.md).

System: a failure-probability model for 240 machines, 6,000 rows, six sensor features. Held-out ROC AUC
is about 0.85 (0.848 when only the model seed varies, 0.849 when split and seed both vary; range up to 0.052,
`reports/lab5-gate-noise.txt`). A run of the whole pipeline took 6 minutes 11 seconds
(`itcs355-training-pipeline-20261022234454`).

### The three strategies, for this system

| Strategy | When it is right here | How it fails here |
|---|---|---|
| **Fixed schedule** | Change is slow and steady, a run is cheap, and a gate decides whether the result is used. All three hold: a run is about 2.5 THB (estimate: 1.5 training + 1 pipeline fee, `reports/lab5-estimate.md`), and a run on unchanged data is rejected by the gate. | It retrains when nothing changed. That is bounded but not free, and I proved it happens: run `…234454` trained on identical data and the gate said `improvement +0.0000 within noise (same data, required +0.0050)`. It is also too slow for a sudden change: a fault on Monday waits until Sunday. And it will train on corrupted data if the corruption is present when it fires. |
| **Data volume threshold** | New machines are onboarded, or labelled failures arrive in bulk, so more data really means a better model. | There is no live feed in this lab: the training file comes from a deterministic generator, so a row counter would never reach its threshold. Even with a feed, a row count says nothing about quality (6,000 more rows from a broken sensor count the same as good rows), and failure labels arrive late, so there can be volume with nothing to learn from (an assumption about the domain, not something I measured). |
| **Drift-triggered** | A real change in the fleet, fast, that hurts the model, with a cheap detector already running. The detector exists: PSI per feature every 10 minutes, and the injected shift was detected in 6 min 57 s (`reports/lab4-postmortem.md`). | The detector cannot tell a real change from a broken feed. Drift is not harm either: the +6 shift on `temp_c` gave PSI 0.383 but AUC moved only from 0.836 to 0.837, so retraining on that alert would have cost money and changed nothing. A change in machine mix gave PSI 0.009 and is invisible to it (Lab 4, Task 5). |

### What I chose

**A fixed weekly schedule, `0 2 * * 0` (Sunday 02:00, Asia/Bangkok), protected by the validate step and the
evaluation gate. Drift raises an alert to a person; it does not start a retrain.**

Why: the two jobs are different. The 10-minute drift detector covers fast change and tells a human within
minutes. The weekly run covers slow change the detector cannot see. At roughly 2.5 THB a run that is about
10 THB a month, and most weeks the gate will reject the result, which costs nothing further. The cadence of one
week is a judgement, not a measurement: nothing in this lab produces new data to tune it against. 02:00
is chosen so that the outcome is waiting for me at the start of the week, not so that it is the quietest hour,
which I have no data on.

### The worst case: drift-triggered retraining on corrupted upstream data

A sensor feed starts sending `temp_c` in the wrong unit, or with a calibration offset. The detector fires within
minutes. If that alert started the pipeline automatically:

1. **A gross fault is stopped.** Fahrenheit values fall outside `PLAUSIBLE_RANGES`, so the `validate` step
   (`tests/test_data.py`) fails and the pipeline aborts before training.
2. **A subtle fault is not.** A +6 offset stays inside every range, so `validate` passes and the pipeline trains
   on corrupted data. The gate compares the new model with the registered one on a test split taken from the
   *same corrupted data*. The data differs, so the unpaired margin (+0.033) applies, and an offset that leaves
   AUC unchanged is rejected. But a corruption that makes the problem easier raises AUC, passes the gate, and is
   registered and deployed to staging.
3. **The damage compounds.** The gate's reference is the most recently registered model. After a bad
   registration that reference is the corrupted model, with an AUC measured on corrupted data. If it is
   inflated, every later good model has to beat it by +0.033, so the gate blocks the recovery.
4. **It is faster than any schedule.** A schedule can do this at most once a week and at a time I chose. A
   drift trigger acts within minutes and fires again on every check while the drift lasts. The old model is not
   deleted, but it is no longer the one in use, and the way back is a manual rollback.

That is why drift only alerts. What exists today: the `validate` contract step, an absolute AUC floor of
0.80, the paired and unpaired margins, and deployment to staging only. What does not exist yet, and would close
the gap in point 2: a frozen reference test set that every candidate is scored on regardless of what data it
trained on, and the `contract.failed` alert proposed in the Lab 4 post-mortem so a broken feed raises a
different alarm from a real shift.

### Fit with the freshness SLO (`monitoring/slo.yaml`)

The Lab 4 SLO caps model age at 30 days and says the Lab 5 schedule must run at least every 21 days, so that a failed
run still leaves 9 days to fix it. A weekly schedule meets that: after a failed run there are 23 days left.

It also leaves a tension that I have to state. The gate rejects a candidate that is no better than the registered
model, so on unchanged data the production model keeps its original training date and the "days since the production
model was trained" clock keeps running even though the pipeline succeeded every week. My decision, which closes the
"revisit in Lab 5" note in the SLO file: the freshness check means "the production model was evaluated against
current data within 30 days", measured from the last pipeline run whose gate evaluated it, whether the candidate was
accepted or rejected as not better. Limit: in this lab the data never changes, so I could not test this reading
against a real change in the data.

## Task 4: Portability

Part A (audit), Part B (a second adapter, `cloudlayer/aws.py`, run against a real AWS account: upload, download and
invoke all pass) and Part C (what was hard, where the abstraction leaked, cost of a full migration, was it worth it):
[reports/lab5-portability.md](reports/lab5-portability.md). Evidence: `reports/lab5-portability-demo.txt`,
`reports/lab5-aws-*.png`, `reports/lab5-aws-s3-listing.txt`.

## Task 5: Cost

TODO: estimate vs actual, optimisation and cost per 1,000 predictions go in `reports/lab5-cost.md`
(the estimate is in `reports/lab5-estimate.md`).

## Task 6: Teardown

TODO: teardown output and the screenshot of the empty resource list.

## Tasks 7 to 9: LLM step

Cost of the managed LLM call, caching and guard decisions: [reports/lab5-llm.md](reports/lab5-llm.md).
