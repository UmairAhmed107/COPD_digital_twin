"""
evaluation.py

Experimental Validation / Evaluation module.

Reference: notes/architecture.md, Section 8

NOTE: Out of scope for the current development step. This file is a
placeholder to be implemented once baseline and proposed twin-state
update mechanisms exist, so they can be compared as described in
architecture.md Section 8:

    Baseline/static ML
            VS
    Simple Twin State
            VS
    Proposed Reliability-Aware Twin

Testing should include controlled conditions such as clean, noisy,
missing, conflicting, multi-source, and anomalous observations.

STATUS: Not implemented. Intentionally empty stub.
"""

from __future__ import annotations

from typing import Any


def evaluate_state_estimation_error(predicted_state: Any, reference_state: Any) -> float:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "evaluation.py is a placeholder. Evaluation is not part of "
        "the current development step."
    )


def run_comparison(methods: list[Any], test_conditions: list[Any]) -> Any:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "evaluation.py is a placeholder. Evaluation is not part of "
        "the current development step."
    )
