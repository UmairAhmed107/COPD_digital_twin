"""
Structural tests for src/simulator.py.

Out of scope for the current development step; confirms only that
the placeholder module imports and its stubs clearly signal
"not implemented".
"""

import pytest

from src import simulator


def test_module_imports():
    assert simulator is not None


def test_clone_state_not_implemented():
    with pytest.raises(NotImplementedError):
        simulator.clone_state(twin_state=None)
