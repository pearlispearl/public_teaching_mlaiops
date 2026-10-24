"""The pipeline DAG itself (Lab 5 Task 1): structure, gate wiring, and compilation."""
from __future__ import annotations

import pytest
import yaml

from cloudlayer import pipelines

STEP_ORDER = ["ingest", "validate", "train", "evaluate", "register", "deploy_staging"]


@pytest.fixture(scope="module")
def spec():
    return pipelines.load_spec()


def steps(spec):
    return {s["name"]: s for s in spec["steps"]}


def test_every_step_in_the_documented_order(spec):
    assert [s["name"] for s in spec["steps"]] == STEP_ORDER


def test_validate_aborts_the_pipeline_on_failure(spec):
    assert steps(spec)["validate"]["on_failure"] == "abort"
    assert steps(spec)["train"]["depends_on"] == ["validate"]


def test_register_is_conditional_on_the_gate_not_unconditional(spec):
    register = steps(spec)["register"]
    assert register["condition"] == "gate_decision == 'pass'"
    assert "gate_decision" in steps(spec)["evaluate"]["outputs"]
    assert register["depends_on"] == ["evaluate"]


def test_deploy_cannot_run_without_register(spec):
    assert steps(spec)["deploy_staging"]["depends_on"] == ["register"]


def test_no_step_uses_the_latest_tag(spec):
    assert all(":latest" not in s["image"] for s in spec["steps"])


def test_gcp_compilation_puts_register_and_deploy_behind_the_condition(spec, tmp_path):
    pytest.importorskip("kfp")
    out = pipelines.compile_gcp(spec, tmp_path / "p.yaml")
    ir = yaml.safe_load(out.read_text())
    root_tasks = ir["root"]["dag"]["tasks"]
    # evaluate and everything before it sit at the root; the guarded steps are inside
    # a condition group, so they are skipped when the gate writes "fail".
    for name in ("ingest", "validate", "train", "evaluate"):
        assert name in root_tasks
    assert "register" not in root_tasks and "deploy-staging" not in root_tasks
    assert any(k.startswith("condition") for k in root_tasks)
    train = ir["deploymentSpec"]["executors"]["exec-train"]["container"]
    assert train["resources"]["cpuLimit"] == 4.0
    text = yaml.safe_dump(ir)
    assert "pipeline_step.py" in text and ":latest" not in text
