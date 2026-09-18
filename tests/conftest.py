import pytest
import pandas as pd

@pytest.fixture
def mock_dataset():
    """Provides an in-memory dataframe matching data_dictionary.md"""
    data = {
        "patient_id": ["P0001", "P0001", "P0002"],
        "visit_number": [1, 2, 1],
        "months_since_baseline": [0.0, 6.0, 0.0],
        "sex": ["M", "M", "F"],
        "age_at_visit": [65.0, 65.5, 70.0],
        "gold_stage_baseline": ["III", "III", "II"],
        "smoking_status_baseline": ["current", "current", "former"],
        "smoking_status_at_visit": ["current", "former", "former"],
        "pack_years": [40.0, 40.0, 20.0],
        "activity_level_at_visit": ["low", "low", "moderate"],
        "bmi": [24.5, 24.5, 28.0],
        "baseline_fev1_liters": [1.5, 1.5, 2.1],
        "baseline_fvc_liters": [2.5, 2.5, 3.0],
        "baseline_fev1_fvc_ratio": [0.6, 0.6, 0.7],
        "fev1_liters": [1.5, 1.45, 2.1],
        "fvc_liters": [2.5, 2.45, 3.0],
        "fev1_fvc_ratio": [0.6, 0.59, 0.7],
        "spo2_pct": [92.0, 93.0, 96.0],
        "cat_score": [20.0, 18.0, 12.0],
        "exacerbations_this_visit": [0, 1, 0],
        "exacerbation_in_next_12m": [1, 0, 0],
        "measurement_source": ["clinic", "home_device", "clinic"],
        "injected_issue": ["none", "none", "missing_spo2"]
    }
    return pd.DataFrame(data)