## LAB2
## Model Promotion Policy

In a real organisation, promotion from **staging to production** should require:

**Who:** A senior ML engineer, not the engineer who trained it.
Separation of duties prevents the same person from training and shipping.

**Evidence required:**
1. Validation metric meets or exceeds the current production model
2. Test metric is not significantly worse than validation (no leakage)
3. Data fingerprint and git commit are recorded and traceable
4. At least one peer has reviewed the comparison report
5. No data drift detected between training data and current production data

## Checkpoint Resume Evidence

Job `1777345977770835968` (2026-09-19) was cancelled after trial 10 completed
(via `gcloud ai custom-jobs cancel`). The checkpoint was synced to GCS after
each trial via `sync_checkpoint_up()`.

When re-submitted as job `4556066947858432000`, the job loaded the checkpoint
from GCS and skipped trials 0–10 immediately, only trials 11–17 were run:
trial 0: already done, skipping (resumed from checkpoint)
trial 1: already done, skipping (resumed from checkpoint)
...
trial 10: already done, skipping (resumed from checkpoint)
trial 11: {'n_estimators': 200, 'max_depth': 12, ...} -> val_roc_auc=0.8446

An interruption costs only the in-progress trial, not the entire study.
Total spend across both jobs: 0.0116 THB.
