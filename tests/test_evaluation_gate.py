"""The registration gate's decision rule (Lab 5 Task 1). Offline: no registry needed."""
from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "evaluation_gate", Path(__file__).resolve().parents[1] / "scripts" / "evaluation_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_below_floor_fails_even_with_no_incumbent():
    ok, _ = gate.decide(0.79, None, paired=False)
    assert not ok


def test_first_registration_passes_when_above_floor():
    ok, why = gate.decide(0.85, None, paired=False)
    assert ok and "first registration" in why


def test_paired_improvement_inside_noise_is_rejected():
    ok, _ = gate.decide(0.8505, 0.8480, paired=True)  # +0.0025: a reseed can do this
    assert not ok


def test_paired_improvement_at_margin_is_accepted():
    ok, _ = gate.decide(0.8480 + gate.MIN_IMPROVEMENT_PAIRED + 1e-9, 0.8480, paired=True)
    assert ok


def test_unpaired_needs_the_larger_margin():
    # +0.01 would pass the paired margin, but with different data it is inside the noise.
    ok, _ = gate.decide(0.86, 0.85, paired=False)
    assert not ok
    ok, _ = gate.decide(0.85 + gate.MIN_IMPROVEMENT_UNPAIRED + 1e-9, 0.85, paired=False)
    assert ok


def test_worse_candidate_is_rejected():
    ok, _ = gate.decide(0.82, 0.85, paired=True)
    assert not ok
