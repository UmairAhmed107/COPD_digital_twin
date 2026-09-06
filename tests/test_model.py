"""
Structural tests for src/model.py.

Out of scope for the current development step; confirms only that
the placeholder module imports and its stubs clearly signal
"not implemented".
"""

import pytest

from src import model


def test_module_imports():
    assert model is not None


def test_train_baseline_model_not_implemented():
    with pytest.raises(NotImplementedError):
        model.train_baseline_model(training_data=None)
