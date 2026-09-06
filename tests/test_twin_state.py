"""
Structural tests for src/twin_state.py.

The twin state update mechanism is the core technical area under
investigation and is not yet implemented. These tests confirm the
module imports, the data structures behave as plain containers, and
the update stub clearly signals "not implemented" rather than
silently applying an unfinished mechanism.
"""

import pytest

from src.twin_state import StateVariable, TwinState, TwinStateVersion


def test_module_imports():
    assert TwinState is not None


def test_state_variable_defaults():
    var = StateVariable(name="FEV1")
    assert var.name == "FEV1"
    assert var.estimated_value is None
    assert var.uncertainty is None
    assert var.historical_information == []


def test_twin_state_starts_empty():
    twin = TwinState(patient_id="patient_001")
    assert twin.patient_id == "patient_001"
    assert twin.history == []
    assert twin.current_state() is None


def test_twin_state_can_store_a_manually_constructed_version():
    twin = TwinState(patient_id="patient_001")
    version = TwinStateVersion(
        version_id=1,
        timestamp="2026-09-02T00:00:00",
        state_values={"FEV1": StateVariable(name="FEV1", estimated_value=2.1)},
        update_method="manual_test_placeholder",
    )
    twin.history.append(version)
    assert twin.current_state() is version
    assert twin.current_state().state_values["FEV1"].estimated_value == 2.1


def test_twin_state_update_not_implemented():
    twin = TwinState(patient_id="patient_001")
    with pytest.raises(NotImplementedError):
        twin.update(observation={"FEV1": 2.1}, method="baseline_replacement")
