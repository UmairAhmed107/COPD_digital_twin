"""
twin_state.py

Twin State Module — CORE TECHNICAL AREA UNDER INVESTIGATION.

Reference: notes/architecture.md, Section 5
Reference: notes/novelty_notes.md, Sections 2-9

Purpose (per architecture.md Section 5.1):
Maintains a persistent, versioned representation of the patient's
current respiratory condition. The state is updated incrementally
when new observations arrive. It must NOT simply replace the
previous state with the latest observation.

IMPORTANT SEPARATION RULE (project rule #4):
Baseline update mechanisms (simple replacement, exponential
smoothing) must be kept clearly separate from the proposed
reliability-aware update mechanism. This file defines the shared
state container and history structures; concrete update strategies
should be implemented as distinct, clearly-labeled functions/classes
(baseline vs. proposed) in a later step, per architecture.md Section
5.4 ("Baseline Update Mechanisms") vs Section 5.3 ("Proposed Initial
Update Mechanism").

NO NOVELTY CLAIM: nothing in this module should be described as
novel. See novelty_notes.md Section 1.

STATUS: Placeholder only. Defines data structures (state variable,
twin state, history entry) matching architecture.md Section 5.2 and
5.5, but no update logic yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StateVariable:
    """
    A single tracked state variable, per architecture.md Section 5.2:

        estimated value
        uncertainty/confidence
        timestamp
        historical information
    """

    name: str
    estimated_value: Optional[float] = None
    uncertainty: Optional[float] = None
    timestamp: Optional[str] = None
    historical_information: list[Any] = field(default_factory=list)


@dataclass
class TwinStateVersion:
    """
    A single version of the twin state history, per architecture.md
    Section 5.5:

        timestamp
        state values
        uncertainty
        incoming observation
        observation source
        reliability score
        update method/version
    """

    version_id: int
    timestamp: Optional[str]
    state_values: dict[str, StateVariable]
    incoming_observation: Optional[Any] = None
    observation_source: Optional[str] = None
    reliability_score: Optional[float] = None
    update_method: Optional[str] = None


class TwinState:
    """
    Persistent, versioned twin state for a single patient.

    NOT YET IMPLEMENTED: update logic.

    This class currently only provides storage for state versions
    (the history chain described in architecture.md Section 5.5).
    Baseline and proposed update mechanisms will be added as
    separate, clearly-labeled methods or functions in a later
    development step, per project rule #4 (keep proposed mechanism
    separate from baselines).
    """

    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        self.history: list[TwinStateVersion] = []

    def current_state(self) -> Optional[TwinStateVersion]:
        """Return the most recent state version, if any."""
        return self.history[-1] if self.history else None

    def update(self, observation: Any, method: str) -> TwinStateVersion:
        """
        NOT YET IMPLEMENTED.

        Placeholder for state update entry point. `method` is
        required and must explicitly identify which update mechanism
        is being used (e.g. "baseline_replacement",
        "baseline_exponential_smoothing", or
        "proposed_reliability_aware_bayesian") so that baseline and
        proposed mechanisms remain distinguishable in the recorded
        history, per architecture.md Section 5.4 and project rule #4.
        """
        raise NotImplementedError(
            "TwinState.update() is a placeholder. The update "
            "mechanism (baseline or proposed) has not been "
            "implemented yet."
        )
