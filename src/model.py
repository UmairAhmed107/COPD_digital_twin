"""
model.py

Progression Model module.

Reference: notes/architecture.md, Section 6

NOTE: Per the current task scope, the progression model is explicitly
NOT being built in this step. This file is a placeholder only, to be
implemented in a later, dedicated step.

Per architecture.md Section 6:
- Initial targets may include FEV1 decline, future respiratory
  state, exacerbation-related risk.
- Initial model: Random Forest / XGBoost, implemented as a baseline
  before considering temporal neural networks.
- The progression model is explicitly NOT the primary novelty target
  (see novelty_notes.md Section 1).

STATUS: Not implemented. Intentionally empty stub.
"""

from __future__ import annotations

from typing import Any


def train_baseline_model(training_data: Any) -> Any:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "model.py is a placeholder. The progression model is not "
        "part of the current development step."
    )


def predict_progression(model: Any, twin_state: Any) -> Any:
    """
    NOT YET IMPLEMENTED. Out of scope for the current development
    step.
    """
    raise NotImplementedError(
        "model.py is a placeholder. The progression model is not "
        "part of the current development step."
    )
