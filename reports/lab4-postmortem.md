# Post-mortem — injected drift on `temp_c`, 2026-10-10

Five lines. Lab 4 grades lines 3 and 4 hardest.

**What fired:**
Policy "ITCS355 feature drift (PSI > 0.10)", condition `PSI temp_c > 0.10`: `custom.googleapis.com/itcs355/drift.psi.temp_c` = 0.38333 (threshold 0.10). Scheduled job logged ALERT at 12:10:30 UTC; incident opened and email received at 12:13:06 UTC. KS was 0.246; the other five features stayed at 0. Detection time from injection (12:06:09 UTC): 6 min 57 s, one trial.

**True cause:**
I injected it: the mean of `temp_c` moved by +6 at 12:06:09 UTC. No real-world change. Data drift injected on purpose (`scripts/inject_drift.py --feature temp_c --mode shift --magnitude 6`); schema and null rate were untouched, so not a broken pipeline.

**Retrain, roll back, or no action — and why:**
No action on the model for now. For a real alert I would first check the schema and null rate of the incoming data and whether the sensor or upstream pipeline broke (calibration, unit change, bad batch), because retraining on corrupted data destroys the last good model. I would retrain only if the checks pass, the shifted distribution persists for days, and it matches a real change in the fleet (for example new equipment). Evidence that would change my mind: a schema or null-rate change (then fix the producer and backfill instead), or a fall in prediction quality without any input change (then it is concept drift).

**What this would have cost if unnoticed for a week:**
An estimate with stated assumptions (`python scripts/estimate_drift_impact.py`). I trained the Lab 1 configuration on the training machines (200 trees, depth 8, seed 20260101) and scored the 1,200 validation rows before and after the same +6 shift. Mean predicted risk goes from 0.104 to 0.126 (+21%), the share of rows above a 0.5 cutoff (my assumption; the service returns only a probability) from 2.08% to 2.58%, and 6% of rows move by more than 0.1. Ranking quality barely changes (AUC 0.836 to 0.837), so a metric that only watches ranking would not notice. At an assumed 1,000 predictions a day that is about 35 extra maintenance flags in a week (0.5 percentage points of 7,000). This assumes the shift is a measurement error, not a real change in the machines, and the model's labels are unchanged. Left alone for a week the fault would also run about 1,440 times longer than the 7 minutes this detector needed.

**How to prevent or detect it faster:**
One concrete change: make `monitoring/run_scheduled.py` run the schema, null-rate and range checks from `tests/test_data.py` on the same current window before it scores drift, and emit a `contract.failed` metric with its own alert. Then a broken upstream feed raises a different alert from a real shift, and nobody retrains on it by reflex. The scheduled detector and email alert stay (detected in about 7 minutes here).
