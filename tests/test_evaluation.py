"""
Structural tests for src/evaluation.py.

Out of scope for the current development step; confirms only that
the placeholder module imports and its stubs clearly signal
"not implemented".
"""

import pytest

from src import evaluation


def test_module_imports():
    assert evaluation is not None


def test_evaluate_state_estimation_error_not_implemented():
    with pytest.raises(NotImplementedError):
        evaluation.evaluate_state_estimation_error(predicted_state=None, reference_state=None)
