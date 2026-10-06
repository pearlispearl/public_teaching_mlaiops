## LAB4

### Task 1: Test categories

Four categories, distinguished by *what makes them fail*:

- **Unit tests** (`tests/test_features.py`, CI step "Unit tests") — test the code in
  `src/data.py`, `src/config.py` and `src/seeds.py` against tiny in-memory inputs. They fail
  when the CODE changes, not when the data changes. Fast, no network, no dataset on disk.
- **Data contract tests** (`tests/test_data.py`, CI step "Data contract tests") — assertions
  about the DATA itself, plus the Lab 1 leakage test. They fail when an upstream producer
  changes something, even with our code untouched.
- **Model behaviour tests** (`tests/test_model_behaviour.py`, CI step "Model behaviour
  tests") — assertions about what the trained model DOES. They fail when its learned
  behaviour changes, independent of any aggregate metric.
- **Integration test** (`.github/workflows/ci.yml`, `build` job) — builds the serving image,
  trains and exports a model, starts the container with `MODEL_VERSION` set to the commit
  SHA, calls `/predict`, and asserts that `probability` is a number in [0, 1] and that
  `model_version` equals the commit SHA. The second assertion is the proof that the image
  being served is the commit under test.

### Data contract tests — incident each one would have caught

| Test | Incident it catches |
|---|---|
| `test_schema_columns_present_and_typed` | An upstream sensor-ingestion change renames or drops `vibration_mm_s`, and the pipeline silently trains on fewer features (or crashes downstream instead of failing loudly here). |
| `test_no_nulls_in_required_columns` | A sensor goes offline and its readings start arriving as nulls; a naive `fillna(0)` downstream would quietly corrupt every feature using that fallback. |
| `test_features_within_plausible_ranges` | A unit-conversion bug (e.g. Fahrenheit shipped instead of Celsius for `temp_c`) ships readings 60-80 points off, inflating risk scores across the whole fleet without an obvious crash. |
| `test_target_is_binary_and_not_degenerate` | An upstream label-generation change collapses `failed_within_7d` to all-zero (e.g. a broken join against the failure log), silently training a model that always predicts "safe". |
| `test_identifier_is_unique` | A duplicate-ingestion bug (e.g. a retried consumer) double-counts some readings, skewing the training distribution. |
| `test_no_machine_leaks_across_splits` (leakage, from Lab 1) | A refactor switches to a row-wise split: validation looks great and never survives production. This is the most common silent failure in this kind of project. |

### Unit tests — what each group protects against

17 tests in `tests/test_features.py`. Property tests of the split that live in
`tests/test_data.py` (`test_split_is_deterministic_given_seed`, `test_split_changes_with_seed`,
`test_every_row_lands_in_exactly_one_split`) run in the data contract step alongside the
leakage test.

| Group | What it protects against |
|---|---|
| `split()`: machine counts per partition, sorted by `reading_id`, independent of input row order | A change to the rounding or slicing in `split()` silently shifts partition sizes, or makes results depend on how the CSV happened to be ordered. |
| `split()` raises `ValueError` on an empty partition | A tiny dataset yields an empty validation set that only shows up much later as a NaN metric, far from the cause. |
| `load_raw()` missing file; `data_fingerprint()` changes with content, not filename | Training on the wrong file, or a fingerprint that fails to change when the data does, which breaks the metric-to-data traceability from Lab 1. |
| `SCHEMA` / `FEATURES` / `PLAUSIBLE_RANGES` consistent | A feature added to training but never added to the contract, so it is never checked. |
| `config.load(strict=True)` raises on missing slots; exported variables beat `cloud.env` | A misconfigured environment that fails late instead of at startup; CI being unable to override a local file. |
| `seeds.set_all()` repeatable, different seeds differ | A seed that is set but not applied, which makes runs irreproducible while the logs claim otherwise. |

### Task 2: CI pipeline

Triggered on pull request and on push to `main`. Job `test`, then job `build` (needs `test`):

```
secret scan (gitleaks, full history, fetch-depth: 0) → lint (ruff) → portability audit
  → unit tests → generate dataset → data contract tests → model behaviour tests
  → service tests
  → [build] build training + serving images, tagged by commit SHA, never `latest`
  → integration test
```

- `BLOB_URI` is set at workflow level so every job receives it (job-level `env` does not
  carry across jobs, which is what broke the integration test the first time).
- Secrets: nothing is stored in a committed file. `permissions: id-token: write` is set for
  OIDC federation.
- Both jobs run on pull requests; image push and staging deploy are intended for `main` only.

### Task 3: Evidence of a blocked bad commit

PR #<เลข PR> (`lab4-bad-contract`, closed without merging) changed one line in
`scripts/make_dataset.py` so the generated CSV dropped the `vibration_mm_s` column:

```python
df.drop(columns=["vibration_mm_s"]).to_csv(args.out, index=False, lineterminator="\n")
```

- **Failing run:** <ลิงก์ของ run ที่แดง>
- **Where it stopped:** step "Data contract tests". Every step before it (secret scan,
  lint, portability audit, unit tests, generate dataset) passed. "Model behaviour tests"
  and "Service tests" did not run, and the `build` job was skipped because of
  `needs: test`, so nothing was built or shipped.
- **Test that caught it:** `test_schema_columns_present_and_typed`
  (`AssertionError: missing columns: ['vibration_mm_s']`). This is the test that
  names the cause.
- **Also failed (as a consequence):** `test_no_nulls_in_required_columns` and
  `test_features_within_plausible_ranges` raised `KeyError` when they tried to read the
  missing column.
- **Unit tests were unaffected:** the 17 tests in `tests/test_features.py` still passed
  locally, which shows the failure came from the data contract, not from the code.

```
FAILED tests/test_data.py::test_schema_columns_present_and_typed - AssertionError: missing columns: ['vibration_mm_s']
FAILED tests/test_data.py::test_no_nulls_in_required_columns - KeyError: "['vibration_mm_s'] not in index"
FAILED tests/test_data.py::test_features_within_plausible_ranges - KeyError: 'vibration_mm_s'
3 failed, 7 passed
```

Screenshot: `docs/images/lab4-blocked-run.png`

### Status

- [x] Unit, data contract, model behaviour and integration tests; CI green on the PR
- [ ] `cd.yml`: push image, deploy to staging, smoke test (still TODO; needs provider OIDC set up)
- [x] Task 3: evidence of a blocked bad commit (PR #<เลข>, closed, not merged)
- [ ] Tasks 4-6: dashboard and SLO, scheduled drift detector, injected drift and post-mortem