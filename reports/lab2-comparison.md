# Lab 2 — Run comparison

Experiment `itcs355-lab2` · 18 trials · total spend 0.0114 THB

`thb_per_point` is cost per percentage point of val_roc_auc above the worst trial. Cheap improvements rank low; expensive improvements rank high, however good the headline number is.

| run_id   |   val_roc_auc |   cost_thb |   n_estimators |   max_depth |   min_samples_leaf |   thb_per_point |
|:---------|--------------:|-----------:|---------------:|------------:|-------------------:|----------------:|
| 0c827012 |        0.8451 |     0.001  |            300 |          12 |                 10 |          0.0008 |
| 5e241b76 |        0.8446 |     0.0008 |            200 |          12 |                 10 |          0.0006 |
| 53a0b9db |        0.8445 |     0.0003 |            100 |          12 |                 10 |          0.0002 |
| 0de3f9a0 |        0.8444 |     0.0003 |            100 |           4 |                 10 |          0.0002 |
| 64445b2c |        0.8428 |     0.0009 |            300 |           8 |                 10 |          0.0008 |
| 940a4ce2 |        0.8426 |     0.0004 |            100 |           4 |                  5 |          0.0004 |
| ba6af6e7 |        0.8422 |     0.0008 |            300 |           4 |                 10 |          0.0008 |
| 76750d34 |        0.8421 |     0.0005 |            200 |           4 |                 10 |          0.0005 |
| 849f2eaf |        0.8417 |     0.0007 |            200 |           8 |                 10 |          0.0007 |
| f607c9bf |        0.8411 |     0.0008 |            300 |           4 |                  5 |          0.0009 |
| b5c4a383 |        0.8405 |     0.0006 |            200 |           4 |                  5 |          0.0007 |
| 76e5e33b |        0.8402 |     0.0004 |            100 |           8 |                 10 |          0.0005 |
| fa0b08e6 |        0.8397 |     0.0003 |            100 |           8 |                  5 |          0.0004 |
| 8a40de0d |        0.8377 |     0.0009 |            300 |           8 |                  5 |          0.0016 |
| 4473a483 |        0.8364 |     0.0006 |            200 |           8 |                  5 |          0.0014 |
| bd48a6ca |        0.8354 |     0.001  |            300 |          12 |                  5 |          0.0031 |
| 4cb6e507 |        0.8352 |     0.0007 |            200 |          12 |                  5 |          0.0023 |
| a830d485 |        0.8322 |     0.0004 |            100 |          12 |                  5 |          0.1243 |

## Which model did you register, and why?

Selected: n_estimators=100, max_depth=12, min_samples_leaf=10, max_features=sqrt
(val_roc_auc=0.8445, cost=0.0003 THB, thb_per_point=0.0002).

**Why not the highest-scoring model:** The best trial (n=300, depth=12, leaf=10,
val_roc_auc=0.8451) costs 0.001 THB, which three times more expensive. A gap this 
small is within seed-level noise for a single-seed evaluation and does not justify 
tripling the compute cost.

**Variance across seeds:** All trials ran on seed=20260101 only. The margin
between selected and best model may be noise rather than a structural improvement.
Multi-seed evaluation would be required to confirm it is real.

**Training cost:** 0.0003 THB per run on n1-standard-4 SPOT. Monthly retraining
at 4 runs per month costs approximately 0.0012 THB.

**One way this choice could be wrong:** max_depth=12 may overfit on production data
that drifts from the training distribution. A shallower tree (depth=4, val=0.8444)
is nearly as accurate and more robust to distributional shift.