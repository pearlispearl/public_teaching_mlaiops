"""Unit tests for preprocessing and config code (Lab 4, Task 1).

Fast, no network, no dataset on disk: every test builds its own tiny input. These are
deliberately different from tests/test_data.py, which asserts properties of the real
dataset. Here we assert properties of the *code*.
"""
from __future__ import annotations

import random

import numpy as np
import pandas as pd
import pytest

from src import config, data, seeds


def _toy_frame(n_machines: int = 10, readings_per_machine: int = 3) -> pd.DataFrame:
    rows = []
    reading_id = 0
    for m in range(n_machines):
        for _ in range(readings_per_machine):
            rows.append({data.ID: reading_id, data.GROUP: m})
            reading_id += 1
    return pd.DataFrame(rows)


# split


def test_split_partitions_have_expected_machine_counts():
    # 10 machines, 0.2/0.2 -> 2 test, 2 val, 6 train. A change to the rounding or the
    # order of slicing in split() shifts these numbers.
    train, val, test = data.split(_toy_frame(10), seed=1)
    assert test[data.GROUP].nunique() == 2
    assert val[data.GROUP].nunique() == 2
    assert train[data.GROUP].nunique() == 6


def test_split_partitions_are_sorted_by_id_and_reindexed():
    # Downstream code assumes a stable row order; sort_values(ID) + reset_index guarantee it.
    for part in data.split(_toy_frame(10), seed=1):
        assert part[data.ID].is_monotonic_increasing
        assert list(part.index) == list(range(len(part)))


def test_split_does_not_depend_on_input_row_order():
    df = _toy_frame(10)
    shuffled = df.sample(frac=1.0, random_state=0).reset_index(drop=True)
    a = data.split(df, seed=7)
    b = data.split(shuffled, seed=7)
    for pa, pb in zip(a, b):
        assert pa[data.ID].tolist() == pb[data.ID].tolist()


def test_split_raises_when_a_partition_would_be_empty():
    # 2 machines with val_frac=0.2 rounds to 0 validation machines. Silently returning an
    # empty validation set would produce a NaN metric much later, far from the cause.
    with pytest.raises(ValueError, match="empty"):
        data.split(_toy_frame(2), seed=1)


# load_raw / hash


def test_load_raw_missing_file_raises_with_actionable_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="make data"):
        data.load_raw(tmp_path / "does_not_exist.csv")


def test_load_raw_reads_csv(tmp_path):
    p = tmp_path / "sensors.csv"
    pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]}).to_csv(p, index=False)
    out = data.load_raw(p)
    assert out.shape == (2, 2)
    assert list(out.columns) == ["a", "b"]


def test_data_fingerprint_changes_when_one_value_changes(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("x,y\n1,2\n3,4\n")
    b.write_text("x,y\n1,2\n3,5\n")
    assert data.data_fingerprint(a) != data.data_fingerprint(b)


def test_data_fingerprint_depends_on_content_not_filename(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("x,y\n1,2\n")
    b.write_text("x,y\n1,2\n")
    assert data.data_fingerprint(a) == data.data_fingerprint(b)


def test_schema_and_feature_list_are_consistent():
    # The contract (SCHEMA, PLAUSIBLE_RANGES) and FEATURES must describe the same columns,
    # otherwise a feature can be trained on without ever being contract-checked.
    assert set(data.FEATURES) <= set(data.SCHEMA)
    assert set(data.FEATURES) == set(data.PLAUSIBLE_RANGES)
    assert data.TARGET in data.SCHEMA
    assert data.TARGET not in data.FEATURES


# config


def test_config_load_strict_raises_when_slots_missing(monkeypatch):
    for slot in config.CAPABILITY_SLOTS:
        monkeypatch.delenv(slot, raising=False)
    with pytest.raises(RuntimeError, match="Missing capability slots"):
        config.load(strict=True)


def test_config_load_non_strict_uses_safe_defaults(monkeypatch):
    for slot in config.CAPABILITY_SLOTS:
        monkeypatch.delenv(slot, raising=False)
    cfg = config.load(strict=False)
    assert cfg.provider == "local"
    assert cfg.mlflow_tracking_uri == "sqlite:///mlflow.db"


def test_config_reads_blob_uri_from_environment(monkeypatch):
    monkeypatch.setenv("BLOB_URI", "file:///tmp/blob")
    assert config.load(strict=False).blob_uri == "file:///tmp/blob"


def test_config_tags_carry_lab_number_for_teardown(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "proj")
    tags = config.load(strict=False).tags(4)
    assert tags == {"course": "itcs355", "student": "proj", "lab": "4"}


def test_env_file_does_not_override_exported_variable(tmp_path, monkeypatch):
    env = tmp_path / "cloud.env"
    env.write_text("# a comment\n\nUT_EXPORTED=from_file\nUT_NEW=from_file\nnot a pair\n")
    monkeypatch.setenv("UT_EXPORTED", "from_shell")
    monkeypatch.setenv("UT_NEW", "placeholder")
    monkeypatch.delenv("UT_NEW")
    config._load_env_file(env)
    import os

    assert os.environ["UT_EXPORTED"] == "from_shell"  # CI must be able to override the file
    assert os.environ["UT_NEW"] == "from_file"


def test_env_file_missing_is_a_noop(tmp_path):
    config._load_env_file(tmp_path / "nope.env")  # must not raise


# seeds


def test_set_all_returns_seed_and_makes_rngs_repeatable(monkeypatch):
    import os

    monkeypatch.setenv("PYTHONHASHSEED", "0")  # restored after the test
    assert seeds.set_all(123) == 123
    first = (random.random(), float(np.random.rand()))
    seeds.set_all(123)
    second = (random.random(), float(np.random.rand()))
    assert first == second
    assert os.environ["PYTHONHASHSEED"] == "123"


def test_set_all_different_seeds_give_different_streams(monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    seeds.set_all(1)
    a = float(np.random.rand())
    seeds.set_all(2)
    b = float(np.random.rand())
    assert a != b