"""
simulator.py

Counterfactual Simulator module.

Reference: notes/architecture.md, Section 7
Reference: notes/novelty_notes.md, Sections 10-11

NOTE: Per the current task scope, the counterfactual simulator is
explicitly NOT being built in this step. This file is a placeholder
only, to be implemented in a later, dedicated step, after the Twin
State Module and Progression Model exist.

Per architecture.md Section 7.2, the intended process is:
    1. Obtain current twin state.
    2. Create a copy of the state.
    3. Apply a defined intervention.
    4. Propagate the modified state through the progression model.
    5. Generate a future trajectory.
    6. Compare it with the baseline trajectory.

The system must preserve the original twin state when generating a
counterfactual branch.

STATUS: Not implemented. Intentionally empty stub.
"""

from __future__ import annotations

from typing import Any


def clone_state(twin_state: Any) -> Any:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "simulator.py is a placeholder. The counterfactual simulator "
        "is not part of the current development step."
    )


def apply_intervention(state_copy: Any, intervention: dict) -> Any:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "simulator.py is a placeholder. The counterfactual simulator "
        "is not part of the current development step."
    )


def compare_trajectories(baseline_trajectory: Any, counterfactual_trajectory: Any) -> Any:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "simulator.py is a placeholder. The counterfactual simulator "
        "is not part of the current development step."
    )
