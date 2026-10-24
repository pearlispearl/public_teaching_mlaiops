"""Deterministic pre-check for the work-order LLM step (Lab 5 Task 8).

Two failures kept reaching the model and being decided by it: a message with no machine_id
(wo-011) and a reading that is physically impossible, such as temp_c=212 (wo-013). A prompt
cannot guarantee either, and the golden set showed it: wo-011 failed in 6 of 6 runs and
wo-013 flipped between runs. Both are decidable from the message alone, using the same
`PLAUSIBLE_RANGES` the data contract tests already enforce, so they are decided here, in
code, before any token is spent.

The guard covers steps 2 and 3 of the prompt (required fields, implausible readings).
Refusals, injection handling and the probability thresholds stay with the model.
"""
from __future__ import annotations

import re
from typing import Any

from src import data

REQUIRED = ("machine_id", "failure_probability")
_FIELD = re.compile(r'(\w+)=("[^"]*"|[^\s"]+)')


def parse_fields(message: str) -> dict[str, str]:
    """Pull key=value pairs out of the message. Quoted values keep their inner text."""
    fields: dict[str, str] = {}
    for key, raw in _FIELD.findall(message):
        value = raw.strip('"') if raw.startswith('"') else raw.rstrip(".,;")
        fields.setdefault(key, value)
    return fields


def precheck(message: str) -> dict[str, Any] | None:
    """Return a finished decision when the message can be decided without the model.

    Returns None when the model should be called.
    """
    fields = parse_fields(message)

    missing = [name for name in REQUIRED if not fields.get(name)]
    if missing:
        return {
            "action": "insufficient_input",
            "summary": f"{', '.join(missing)} missing; cannot draft a work order.",
        }

    try:
        probability = float(fields["failure_probability"])
    except ValueError:
        probability = float("nan")
    if not 0.0 <= probability <= 1.0:
        return {
            "action": "insufficient_input",
            "summary": (f"failure_probability={fields['failure_probability']} is invalid: "
                        "it must be between 0 and 1."),
        }

    for name, (low, high) in data.PLAUSIBLE_RANGES.items():
        if name not in fields:
            continue
        try:
            value = float(fields[name])
        except ValueError:
            value = float("nan")
        if not low <= value <= high:
            return {
                "action": "escalate_to_engineer",
                "summary": (f"{name}={fields[name]} is implausible (plausible range "
                            f"{low:g} to {high:g}); likely a unit or sensor error."),
            }
    return None
