"""Unit tests for TwinState tracking module.

Tests state initialization, property integrity, and add_visit history appending.
"""

import copy
import pandas as pd
import pytest

from src.twin_state import TwinState, STATIC_FIELDS


@pytest.fixture
def sample_static_data():
    return {
        "patient_id": "P0001",
        "sex": "M",
        "age_at_baseline": 65.0,
        "gold_stage_baseline": "III (Severe)",
        "smoking_status_baseline": "current",
        "pack_years": 40.0,
        "baseline_fev1_liters": 1.5,
        "baseline_fvc_liters": 2.5,
        "baseline_fev1_fvc_ratio": 0.6,
        "bmi": 24.5,
    }


@pytest.fixture
def sample_visit_1():
    return {
        "visit_number": 1,
        "months_since_baseline": 0.0,
        "age_at_visit": 65.0,
        "smoking_status_at_visit": "current",
        "activity_level_at_visit": "low",
        "fev1_liters": 1.50,
        "fvc_liters": 2.50,
        "fev1_fvc_ratio": 0.60,
        "spo2_pct": 92.0,
        "cat_score": 20.0,
        "exacerbations_this_visit": 0,
        "measurement_source": "clinic",
    }


@pytest.fixture
def sample_visit_2():
    return {
        "visit_number": 2,
        "months_since_baseline": 6.0,
        "age_at_visit": 65.5,
        "smoking_status_at_visit": "former",
        "activity_level_at_visit": "moderate",
        "fev1_liters": 1.45,
        "fvc_liters": 2.45,
        "fev1_fvc_ratio": 0.59,
        "spo2_pct": 93.0,
        "cat_score": 18.0,
        "exacerbations_this_visit": 1,
        "measurement_source": "home_device",
    }


def test_twin_state_initialization(sample_static_data, sample_visit_1):
    """Verify TwinState correctly initializes patient_id, static, current, and history."""
    twin = TwinState(
        static_data=sample_static_data,
        initial_visit=sample_visit_1,
        patient_id="P0001",
    )

    # Check properties
    assert twin.patient_id == "P0001"
    assert isinstance(twin.static, dict)
    assert isinstance(twin.current, dict)
    assert isinstance(twin.history, list)

    # Static data integrity
    assert twin.static["sex"] == "M"
    assert twin.static["baseline_fev1_liters"] == 1.5

    # History starts with exactly the initial visit
    assert len(twin.history) == 1
    assert twin.history[0]["visit_number"] == 1
    assert twin.history[0]["months_since_baseline"] == 0.0

    # Current state matches initial visit
    assert twin.current["visit_number"] == 1
    assert twin.current["fev1_liters"] == 1.50
    assert twin.current["smoking_status_at_visit"] == "current"


def test_twin_state_add_visit(sample_static_data, sample_visit_1, sample_visit_2):
    """Verify add_visit updates current state and appends to history list."""
    twin = TwinState(
        static_data=sample_static_data,
        initial_visit=sample_visit_1,
    )

    assert len(twin.history) == 1
    assert twin.current["visit_number"] == 1

    # Add second visit
    twin.add_visit(sample_visit_2)

    # History should now contain 2 visits
    assert len(twin.history) == 2
    assert twin.history[0]["visit_number"] == 1
    assert twin.history[1]["visit_number"] == 2

    # Current state should now be visit 2
    assert twin.current["visit_number"] == 2
    assert twin.current["months_since_baseline"] == 6.0
    assert twin.current["smoking_status_at_visit"] == "former"
    assert twin.current["activity_level_at_visit"] == "moderate"
    assert twin.current["fev1_liters"] == 1.45

    # Static baseline remains untouched
    assert twin.static["smoking_status_baseline"] == "current"
    assert twin.static["baseline_fev1_liters"] == 1.5


def test_twin_state_deep_copy_isolation(sample_static_data, sample_visit_1, sample_visit_2):
    """Verify mutating outside dictionaries does not corrupt TwinState internal state."""
    static_copy = copy.deepcopy(sample_static_data)
    visit_copy = copy.deepcopy(sample_visit_1)

    twin = TwinState(static_data=static_copy, initial_visit=visit_copy)

    # Mutate external dicts
    static_copy["sex"] = "MUTATED"
    visit_copy["fev1_liters"] = 999.0

    assert twin.static["sex"] == "M"
    assert twin.current["fev1_liters"] == 1.50
    assert twin.history[0]["fev1_liters"] == 1.50


def test_twin_state_to_dict_and_from_dict(sample_static_data, sample_visit_1, sample_visit_2):
    """Verify serialization to dict and reconstruction from dict."""
    twin = TwinState(static_data=sample_static_data, initial_visit=sample_visit_1)
    twin.add_visit(sample_visit_2)

    serialized = twin.to_dict()
    assert serialized["patient_id"] == "P0001"
    assert "static" in serialized
    assert "current" in serialized
    assert len(serialized["history"]) == 2

    # Reconstruct from serialized dict
    reconstructed = TwinState.from_dict(serialized)
    assert reconstructed.patient_id == "P0001"
    assert len(reconstructed.history) == 2
    assert reconstructed.current["visit_number"] == 2
    assert reconstructed.current["fev1_liters"] == 1.45


def test_twin_state_from_dataframe(mock_dataset):
    """Verify constructing TwinState from mock_dataset records for patient P0001."""
    p1_df = mock_dataset[mock_dataset["patient_id"] == "P0001"]
    assert len(p1_df) == 2

    twin = TwinState.from_dataframe(p1_df)

    assert twin.patient_id == "P0001"
    assert len(twin.history) == 2
    assert twin.history[0]["visit_number"] == 1
    assert twin.history[1]["visit_number"] == 2
    assert twin.current["visit_number"] == 2
    assert twin.static["sex"] == "M"


def test_twin_state_validation_errors(mock_dataset):
    """Verify error handling on invalid inputs."""
    # Missing patient_id
    with pytest.raises(ValueError, match="valid 'patient_id'"):
        TwinState(static_data={}, initial_visit={})

    # Empty DataFrame
    with pytest.raises(ValueError, match="empty DataFrame"):
        TwinState.from_dataframe(pd.DataFrame())

    # Multi-patient DataFrame
    with pytest.raises(ValueError, match="records for exactly 1 patient"):
        TwinState.from_dataframe(mock_dataset)
