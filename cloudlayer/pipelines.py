"""Lab 5 — compile pipeline/pipeline.yaml into your provider's pipeline service.

This module is Layer 3, so provider SDKs are allowed here and nowhere else. The DAG stays
in YAML; only the translation lives here. That separation is what you argue for or against
in Lab 5 Task 4.

Implement ONE compile function, for your provider.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

SPEC = Path(__file__).resolve().parents[1] / "pipeline" / "pipeline.yaml"


def load_spec(path: Path = SPEC) -> dict[str, Any]:
    """Read the neutral DAG and expand ${VAR} references from the environment."""
    raw = path.read_text()
    os.environ.setdefault("TRAIN_INSTANCE", "n1-standard-4")
    os.environ.setdefault("IMAGE_TAG", "dev")
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)
    return yaml.safe_load(raw)


def compile_aws(spec: dict[str, Any]):
    """SageMaker Pipelines.

    Each step becomes a ProcessingStep or TrainingStep; `condition` becomes a
    ConditionStep. Note that SageMaker's condition steps branch rather than abort, so
    `on_failure: abort` needs a FailStep on the else branch — an asymmetry worth
    mentioning in your Lab 5 write-up.
    """
    raise NotImplementedError("TODO Lab 5: build a sagemaker.workflow.pipeline.Pipeline")


def compile_azure(spec: dict[str, Any]):
    """Azure ML Pipelines.

    Each step becomes a command component; the DAG is expressed as a @pipeline function.
    Conditions use azure.ai.ml.dsl.condition, which is closer to this YAML than the other
    two providers' equivalents.
    """
    raise NotImplementedError("TODO Lab 5: build an azure.ai.ml pipeline job")


def _component_yaml(step: dict[str, Any], run_id_input: str, decision_output: str | None) -> str:
    """One step as a KFP container component. The step logic is in the image."""
    args = ["--run-id", {"inputValue": run_id_input}]
    spec: dict[str, Any] = {
        "name": step["name"],
        "inputs": [{"name": run_id_input, "type": "String"}],
        "implementation": {"container": {
            "image": step["image"], "command": step["command"], "args": args}},
    }
    if decision_output:
        spec["outputs"] = [{"name": decision_output, "type": "String"}]
        args += ["--decision-out", {"outputPath": decision_output}]
    return yaml.safe_dump(spec, sort_keys=False)


def _condition(step: dict[str, Any]):
    """Parse `<output> == '<value>'` into (output, value), or None."""
    raw = step.get("condition")
    if not raw:
        return None
    match = re.fullmatch(r"\s*(\w+)\s*==\s*'([^']*)'\s*", raw)
    if not match:
        raise ValueError(f"Unsupported condition {raw!r}; use  <output> == '<value>'")
    return match.group(1), match.group(2)


_MACHINES = {"n1-standard-4": ("4", "15G"), "n1-standard-8": ("8", "30G")}


def compile_gcp(spec: dict[str, Any], out_path: str | Path | None = None) -> Path:
    """Vertex AI Pipelines.

    Kubeflow Pipelines underneath: steps become container components, conditions become
    dsl.If blocks. The compiled artifact is a JSON file you submit, so this builds a file
    and returns its path. Submit it with scripts/run_pipeline.py.

    Limits, stated honestly: `spot: true` is not applied (Vertex Pipelines needs a custom-job
    wrapper for spot VMs), and every step runs on the pipeline default machine unless the
    step names an `instance` we can map to cpu and memory limits.
    """
    from kfp import compiler, components, dsl

    from src import config

    spec = load_spec() if spec is None else spec
    steps = {s["name"]: s for s in spec["steps"]}

    # An output that a condition reads becomes a real pipeline output; the others are
    # documentation of what the step leaves in BLOB_URI.
    decision_of: dict[str, str | None] = {n: None for n in steps}
    for step in steps.values():
        cond = _condition(step)
        if cond:
            producer = next(d for d in step.get("depends_on", [])
                            if cond[0] in steps[d].get("outputs", []))
            decision_of[producer] = cond[0]

    factories = {
        name: components.load_component_from_text(
            _component_yaml(step, "run_id", decision_of[name]))
        for name, step in steps.items()}

    # A step is conditional if it, or anything it depends on, has a condition.
    def guard(name: str):
        cond = _condition(steps[name])
        if cond:
            return cond
        for dep in steps[name].get("depends_on", []):
            inherited = guard(dep)
            if inherited:
                return inherited
        return None

    order: list[str] = []
    while len(order) < len(steps):
        for name, step in steps.items():
            if name not in order and all(d in order for d in step.get("depends_on", [])):
                order.append(name)

    passthrough = (*config.CAPABILITY_SLOTS, "SERVE_IMAGE", "SERVE_SERVICE_ACCOUNT", "SERVE_INSTANCE")
    slots = {s: os.environ[s] for s in passthrough if os.environ.get(s)}

    @dsl.pipeline(name=spec["name"])
    def pipeline():
        tasks: dict[str, Any] = {}

        def make(name: str):
            task = factories[name](run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER)
            for dep in steps[name].get("depends_on", []):
                task.after(tasks[dep])
            for key, value in slots.items():
                task.set_env_variable(key, value)
            task.set_caching_options(False)
            cpu_mem = _MACHINES.get(str(steps[name].get("instance", "")))
            if cpu_mem:
                task.set_cpu_limit(cpu_mem[0]).set_memory_limit(cpu_mem[1])
            tasks[name] = task

        unconditional = [n for n in order if not guard(n)]
        conditional = [n for n in order if guard(n)]
        for name in unconditional:
            make(name)
        if conditional:
            conds = {guard(n) for n in conditional}
            if len(conds) != 1:
                raise ValueError("Only one distinct condition per pipeline is supported")
            output, value = conds.pop()
            producer = next(n for n, o in decision_of.items() if o == output)
            with dsl.If(tasks[producer].outputs[output] == value):
                for name in conditional:
                    make(name)

    out = Path(out_path or Path(__file__).resolve().parents[1] / "pipeline" / "compiled_gcp.yaml")
    compiler.Compiler().compile(pipeline, package_path=str(out))
    return out


COMPILERS = {"aws": compile_aws, "azure": compile_azure, "gcp": compile_gcp}


def compile_for(provider: str, spec: dict[str, Any] | None = None):
    spec = spec or load_spec()
    try:
        return COMPILERS[provider.lower()](spec)
    except KeyError:
        raise ValueError(f"No pipeline compiler for {provider!r}") from None
