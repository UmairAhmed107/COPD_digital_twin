"""Unit tests for COPD Digital Twin trajectory simulator.

Verifies:
- Future trajectory generation across time horizons.
- What-if interventions (smoking cessation, increased activity).
- Custom scenario overrides.
- Model interoperability (Random Forest & XGBoost).
- Boundary conditions and input validation (zero horizon, invalid intervals).
"""

import pandas as pd
import pytest

from src.twin_state import TwinState
from src.simulator import (
    PRESET_SCENARIOS,
    build_features_for_time_point,
    build_scenario_overrides,
    generate_time_points,
    simulate_trajectory,
)


@pytest.fixture
def smoker_twin():
    """Twin for a currently-smoking patient with visit 1 at month 0."""
    static = {
        "patient_id": "P0001",
        "sex": "M",
        "age_at_baseline": 65.0,
        "gold_stage_baseline": "III (Severe)",
        "smoking_status_baseline": "current",
        "pack_years": 40.0,
        "baseline_fev1_liters": 1.50,
        "baseline_fvc_liters": 2.50,
        "baseline_fev1_fvc_ratio": 0.60,
        "bmi": 24.5,
    }
    visit = {
        "visit_number": 1,
        "months_since_baseline": 0.0,
        "age_at_visit": 65.0,
        "smoking_status_at_visit": "current",
        "activity_level_at_visit": "low",
        "fev1_liters": 1.50,
        "fvc_liters": 2.50,
        "fev1_fvc_ratio": 0.60,
    }
    return TwinState(static_data=static, initial_visit=visit)


@pytest.fixture
def multi_visit_twin(smoker_twin):
    """Twin with 2 visits, current visit at month 6."""
    visit2 = {
        "visit_number": 2,
        "months_since_baseline": 6.0,
        "age_at_visit": 65.5,
        "smoking_status_at_visit": "current",
        "activity_level_at_visit": "low",
        "fev1_liters": 1.45,
        "fvc_liters": 2.45,
        "fev1_fvc_ratio": 0.59,
    }
    twin = TwinState(smoker_twin.static, smoker_twin.current)
    twin.add_visit(visit2)
    return twin


def test_generate_time_points():
    """Verify time point generator handles standard intervals and edge cases."""
    pts = generate_time_points(start_month=0.0, horizon_months=36, step_months=6)
    assert pts == [0.0, 6.0, 12.0, 18.0, 24.0, 30.0, 36.0]

    # Non-zero start
    pts_offset = generate_time_points(start_month=6.0, horizon_months=12, step_months=6)
    assert pts_offset == [6.0, 12.0, 18.0]

    # Zero horizon -> single point
    pts_zero = generate_time_points(start_month=12.0, horizon_months=0, step_months=6)
    assert pts_zero == [12.0]

    # Invalid arguments
    with pytest.raises(ValueError, match="step_months must be positive"):
        generate_time_points(0.0, 36, 0)
    with pytest.raises(ValueError, match="step_months must be positive"):
        generate_time_points(0.0, 36, -6)
    with pytest.raises(ValueError, match="horizon_months must be non-negative"):
        generate_time_points(0.0, -12, 6)


def test_build_features_for_time_point(smoker_twin):
    """Verify feature construction advances age and applies overrides."""
    # Month 0: age should be 65.0
    f0 = build_features_for_time_point(smoker_twin, t=0.0, overrides={})
    assert f0["age_at_visit"] == 65.0
    assert f0["months_since_baseline"] == 0.0
    assert f0["smoking_status_at_visit"] == "current"
    assert f0["activity_level_at_visit"] == "low"

    # Month 24: age should be 67.0
    f24 = build_features_for_time_point(
        smoker_twin,
        t=24.0,
        overrides={"smoking_status_at_visit": "former", "activity_level_at_visit": "high"},
    )
    assert f24["age_at_visit"] == 67.0
    assert f24["months_since_baseline"] == 24.0
    assert f24["smoking_status_at_visit"] == "former"
    assert f24["activity_level_at_visit"] == "high"


def test_simulate_trajectory_baseline(smoker_twin):
    """Verify baseline trajectory projection forward 36 months."""
    results = simulate_trajectory(
        twin_state=smoker_twin,
        horizon_months=36,
        step_months=6,
        scenario_modifications=["baseline"],
        model_type="random_forest",
    )

    assert "baseline" in results
    traj = results["baseline"]
    assert len(traj) == 7  # 0, 6, 12, 18, 24, 30, 36

    # Verify time points
    months = [p["months_since_baseline"] for p in traj]
    assert months == [0, 6, 12, 18, 24, 30, 36]

    # Verify predictions are valid floats
    for p in traj:
        assert isinstance(p["predicted_fev1_liters"], float)
        assert 0.2 <= p["predicted_fev1_liters"] <= 5.0
        assert "exacerbation_risk_pct" in p
        assert isinstance(p["exacerbation_risk_pct"], float)
        assert 0.0 <= p["exacerbation_risk_pct"] <= 100.0


def test_simulate_trajectory_what_if_scenarios(smoker_twin):
    """Verify multiple scenarios project simultaneously and show expected intervention effects."""
    scenarios = ["baseline", "smoking_cessation", "increased_activity"]
    results = simulate_trajectory(
        twin_state=smoker_twin,
        horizon_months=36,
        step_months=6,
        scenario_modifications=scenarios,
        model_type="random_forest",
    )

    for sc in scenarios:
        assert sc in results
        assert len(results[sc]) == 7

    # At month 36, smoking cessation or increased activity should generally preserve or improve FEV1
    base_m36 = results["baseline"][-1]["predicted_fev1_liters"]
    cess_m36 = results["smoking_cessation"][-1]["predicted_fev1_liters"]
    act_m36 = results["increased_activity"][-1]["predicted_fev1_liters"]

    assert cess_m36 >= base_m36 - 0.05  # Intervention should not drastically worsen lung function

    # Verify exacerbation risk attenuation: smoking cessation lowers flare-up risk vs baseline
    base_risk = results["baseline"][-1]["exacerbation_risk_pct"]
    cess_risk = results["smoking_cessation"][-1]["exacerbation_risk_pct"]
    assert cess_risk <= base_risk


def test_simulate_trajectory_both_models(smoker_twin):
    """Verify simulation works for both Random Forest and XGBoost."""
    res_rf = simulate_trajectory(
        twin_state=smoker_twin,
        horizon_months=12,
        step_months=6,
        scenario_modifications=["baseline"],
        model_type="random_forest",
    )

    res_xgb = simulate_trajectory(
        twin_state=smoker_twin,
        horizon_months=12,
        step_months=6,
        scenario_modifications=["baseline"],
        model_type="xgboost",
    )

    assert len(res_rf["baseline"]) == 3
    assert len(res_xgb["baseline"]) == 3
    assert abs(res_rf["baseline"][0]["predicted_fev1_liters"] - res_xgb["baseline"][0]["predicted_fev1_liters"]) < 0.5


def test_simulate_custom_scenarios(smoker_twin):
    """Verify custom scenario dictionary with arbitrary field overrides."""
    custom_scenarios = {
        "baseline": {},
        "target_weight_loss": {"bmi": 21.0},
        "lifestyle_change": {
            "smoking_status_at_visit": "former",
            "activity_level_at_visit": "high",
        },
    }
    results = simulate_trajectory(
        twin_state=smoker_twin,
        horizon_months=24,
        step_months=6,
        scenario_modifications=custom_scenarios,
    )

    assert set(results.keys()) == {"baseline", "target_weight_loss", "lifestyle_change"}
    assert len(results["target_weight_loss"]) == 5


def test_simulate_multi_visit_start_time(multi_visit_twin):
    """Verify start_from_current begins simulation from the patient's latest visit month."""
    # Current visit is at month 6.0
    res_current = simulate_trajectory(
        twin_state=multi_visit_twin,
        horizon_months=12,
        step_months=6,
        start_from_current=True,
    )
    # Starts at 6, then 12, 18
    months_curr = [p["months_since_baseline"] for p in res_current["baseline"]]
    assert months_curr == [6, 12, 18]

    # start_from_current=False starts at month 0
    res_zero = simulate_trajectory(
        twin_state=multi_visit_twin,
        horizon_months=12,
        step_months=6,
        start_from_current=False,
    )
    months_zero = [p["months_since_baseline"] for p in res_zero["baseline"]]
    assert months_zero == [0, 6, 12]


def test_simulate_edge_cases(smoker_twin):
    """Verify edge case handling for invalid inputs and zero horizons."""
    # Zero horizon -> exactly 1 point
    res_zero_horizon = simulate_trajectory(
        twin_state=smoker_twin,
        horizon_months=0,
        step_months=6,
    )
    assert len(res_zero_horizon["baseline"]) == 1
    assert res_zero_horizon["baseline"][0]["months_since_baseline"] == 0

    # Invalid step_months
    with pytest.raises(ValueError, match="step_months must be positive"):
        simulate_trajectory(smoker_twin, horizon_months=36, step_months=0)

    # Invalid horizon_months
    with pytest.raises(ValueError, match="horizon_months must be non-negative"):
        simulate_trajectory(smoker_twin, horizon_months=-10, step_months=6)

    # Invalid twin_state
    with pytest.raises(TypeError, match="Expected a TwinState instance"):
        simulate_trajectory({"invalid": "dict"}, horizon_months=12, step_months=6)


def test_simulate_never_smoker_cessation():
    """Verify smoking cessation scenario for a never-smoker preserves 'never' status."""
    static = {
        "patient_id": "P0003",
        "sex": "F",
        "age_at_baseline": 70.0,
        "gold_stage_baseline": "I (Mild)",
        "smoking_status_baseline": "never",
        "pack_years": 0.0,
        "baseline_fev1_liters": 2.2,
        "bmi": 23.0,
    }
    visit = {
        "visit_number": 1,
        "months_since_baseline": 0.0,
        "age_at_visit": 70.0,
        "smoking_status_at_visit": "never",
        "activity_level_at_visit": "moderate",
        "fev1_liters": 2.2,
    }
    never_twin = TwinState(static_data=static, initial_visit=visit)

    overrides = build_scenario_overrides(never_twin, ["smoking_cessation"])
    assert overrides["smoking_cessation"]["smoking_status_at_visit"] == "never"
