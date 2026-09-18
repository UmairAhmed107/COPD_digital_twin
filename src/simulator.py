"""Future trajectory simulation and what-if scenario engine for COPD Digital Twin.

Sweeps time forward from a patient's current twin state and projects future
lung function (`fev1_liters`) using the trained machine learning models.
Supports behavioral and clinical intervention scenarios (e.g. smoking cessation,
increased physical activity).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

try:
    from src.twin_state import TwinState
    from src.model import predict_fev1, predict_exacerbation_risk, DEFAULT_ARTIFACTS_DIR
except ImportError:
    from twin_state import TwinState
    from model import predict_fev1, predict_exacerbation_risk, DEFAULT_ARTIFACTS_DIR

# Standard pre-configured scenario names and modifications
PRESET_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "baseline": {},
    "smoking_cessation": {"smoking_status_at_visit": "former"},
    "increased_activity": {"activity_level_at_visit": "high"},
    "combined_intervention": {
        "smoking_status_at_visit": "former",
        "activity_level_at_visit": "high",
    },
}


def build_scenario_overrides(
    twin_state: TwinState,
    scenario_input: Optional[Union[List[str], Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Normalize scenario input into a dictionary of scenario names to field overrides.

    Parameters
    ----------
    twin_state : TwinState
        Current patient twin state.
    scenario_input : Optional[Union[List[str], Dict[str, Any]]]
        Can be:
        - None: defaults to ["baseline", "smoking_cessation", "increased_activity"]
        - List of scenario names (e.g. ["baseline", "smoking_cessation"])
        - Dict of {scenario_name: {field: new_value}}
        - Dict of single scenario modifications {field: new_value}

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Normalized map of scenario_name -> field overrides dict.
    """
    if scenario_input is None:
        scenario_names = ["baseline", "smoking_cessation", "increased_activity"]
        return {name: PRESET_SCENARIOS.get(name, {}) for name in scenario_names}

    if isinstance(scenario_input, list):
        scenarios: Dict[str, Dict[str, Any]] = {}
        for name in scenario_input:
            if name in PRESET_SCENARIOS:
                override = PRESET_SCENARIOS[name].copy()
                # If patient is never-smoker, smoking cessation remains never
                if name == "smoking_cessation" and twin_state.current.get("smoking_status_at_visit") == "never":
                    override["smoking_status_at_visit"] = "never"
                scenarios[name] = override
            else:
                scenarios[name] = {}
        return scenarios

    if isinstance(scenario_input, dict):
        # Check if it's a dict of dicts (e.g. {"scen1": {"col": val}})
        is_nested = any(isinstance(v, dict) for v in scenario_input.values())
        if is_nested:
            return {k: v.copy() if isinstance(v, dict) else {} for k, v in scenario_input.items()}
        # Single scenario override dict: create baseline and intervention
        return {
            "baseline": {},
            "intervention": scenario_input.copy(),
        }

    raise TypeError(
        f"Unsupported scenario_modifications type: {type(scenario_input)}. "
        f"Expected None, list of strings, or dictionary."
    )


def generate_time_points(
    start_month: float,
    horizon_months: int,
    step_months: int,
) -> List[float]:
    """Generate discrete monthly time points for trajectory sweeping.

    Parameters
    ----------
    start_month : float
        Initial time point (typically current visit's months_since_baseline).
    horizon_months : int
        Number of future months to project forward.
    step_months : int
        Time step between trajectory points.

    Returns
    -------
    List[float]
        Ordered list of time points.
    """
    if step_months <= 0:
        raise ValueError(f"step_months must be positive and non-zero, got: {step_months}")
    if horizon_months < 0:
        raise ValueError(f"horizon_months must be non-negative, got: {horizon_months}")

    if horizon_months == 0:
        return [round(start_month, 1)]

    points = []
    curr = float(start_month)
    end = float(start_month + horizon_months)

    while curr <= end + 1e-5:
        points.append(round(curr, 1))
        curr += step_months

    return points


def build_features_for_time_point(
    twin_state: TwinState,
    t: float,
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct the 9 approved feature values for a twin state at a future time point.

    Parameters
    ----------
    twin_state : TwinState
        Patient twin state.
    t : float
        Future months_since_baseline.
    overrides : Dict[str, Any]
        Scenario feature modifications (e.g. smoking cessation).

    Returns
    -------
    Dict[str, Any]
        Dictionary matching the approved input feature schema.
    """
    # 1. Base static fields
    sex = twin_state.static.get("sex", twin_state.current.get("sex", "M"))
    gold_stage = twin_state.static.get(
        "gold_stage_baseline", twin_state.current.get("gold_stage_baseline", "II")
    )
    pack_years = float(
        twin_state.static.get("pack_years", twin_state.current.get("pack_years", 0.0))
    )
    bmi = float(twin_state.static.get("bmi", twin_state.current.get("bmi", 25.0)))
    baseline_fev1 = float(
        twin_state.static.get(
            "baseline_fev1_liters",
            twin_state.current.get("baseline_fev1_liters", 2.0),
        )
    )

    # 2. Time-varying fields (defaults from current visit)
    smoking_status = twin_state.current.get("smoking_status_at_visit", "former")
    activity_level = twin_state.current.get("activity_level_at_visit", "moderate")

    # 3. Dynamic age progression
    if "age_at_baseline" in twin_state.static:
        base_age = float(twin_state.static["age_at_baseline"])
        age_at_t = round(base_age + (t / 12.0), 1)
    elif "age_at_visit" in twin_state.current:
        curr_age = float(twin_state.current["age_at_visit"])
        curr_m = float(twin_state.current.get("months_since_baseline", 0.0))
        age_at_t = round(curr_age + ((t - curr_m) / 12.0), 1)
    else:
        age_at_t = 65.0

    # 4. Construct base feature record
    features = {
        "age_at_visit": age_at_t,
        "sex": sex,
        "gold_stage_baseline": gold_stage,
        "smoking_status_at_visit": smoking_status,
        "pack_years": pack_years,
        "activity_level_at_visit": activity_level,
        "bmi": bmi,
        "months_since_baseline": float(t),
        "baseline_fev1_liters": baseline_fev1,
    }

    # 5. Apply scenario overrides
    for k, v in overrides.items():
        if k in features:
            features[k] = v

    return features


def simulate_trajectory(
    twin_state: TwinState,
    horizon_months: int = 36,
    step_months: int = 6,
    scenario_modifications: Optional[Union[List[str], Dict[str, Any]]] = None,
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    model_type: str = "random_forest",
    start_from_current: bool = True,
    preprocessor: Optional[Any] = None,
    model: Optional[Any] = None,
    classifier: Optional[Any] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Simulate future lung function trajectories and exacerbation risks for multiple clinical scenarios.

    Sweeps months_since_baseline forward from current twin state up to horizon_months
    in step_months increments, calling predict_fev1 and predict_exacerbation_risk for each scenario.

    Parameters
    ----------
    twin_state : TwinState
        The patient's digital twin state holding static identity and current visit.
    horizon_months : int, default=36
        Projection horizon in months (e.g. 36 = 3 years).
    step_months : int, default=6
        Step interval in months (e.g. every 6 months).
    scenario_modifications : Optional[Union[List[str], Dict[str, Any]]], default=None
        Scenarios to simulate. Can be:
        - None: runs default scenarios ("baseline", "smoking_cessation", "increased_activity")
        - List of scenario names (e.g. ["baseline", "smoking_cessation"])
        - Dict of {scenario_name: {feature_override_dict}}
    artifacts_dir : Union[str, Path], default='artifacts'
        Path to stored model and preprocessor joblib files.
    model_type : str, default='random_forest'
        Regression model: 'random_forest' (or 'rf') / 'xgboost' (or 'xgb').
    start_from_current : bool, default=True
        If True, begins simulation at twin_state.current['months_since_baseline'].
        If False, begins at month 0.0.
    preprocessor : Optional[Any]
        Pre-loaded fitted ColumnTransformer (optional override).
    model : Optional[Any]
        Pre-loaded regression model (optional override).
    classifier : Optional[Any]
        Pre-loaded exacerbation classification model (optional override).

    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        Dictionary mapping scenario name to list of trajectory points:
        {
            "baseline": [
                {
                    "months_since_baseline": 0,
                    "predicted_fev1_liters": 1.5032,
                    "exacerbation_risk_pct": 74.0
                },
                ...
            ],
            ...
        }
    """
    if not hasattr(twin_state, "static") or not hasattr(twin_state, "current"):
        raise TypeError(f"Expected a TwinState instance, received: {type(twin_state)}")

    # Determine starting time
    if start_from_current:
        start_month = float(twin_state.current.get("months_since_baseline", 0.0))
    else:
        start_month = 0.0

    time_points = generate_time_points(
        start_month=start_month,
        horizon_months=horizon_months,
        step_months=step_months,
    )

    scenarios = build_scenario_overrides(twin_state, scenario_modifications)
    results: Dict[str, List[Dict[str, Any]]] = {}

    for scenario_name, overrides in scenarios.items():
        # Build feature DataFrame for all time points in this scenario
        rows = [
            build_features_for_time_point(twin_state, t, overrides)
            for t in time_points
        ]
        df_scenario = pd.DataFrame(rows)

        # Batch predict all trajectory points using the regressor
        predictions = predict_fev1(
            features=df_scenario,
            model_type=model_type,
            artifacts_dir=artifacts_dir,
            preprocessor=preprocessor,
            model=model,
        )

        # Batch predict exacerbation risk probability
        try:
            exac_risks = predict_exacerbation_risk(
                features=df_scenario,
                artifacts_dir=artifacts_dir,
                preprocessor=preprocessor,
                classifier=classifier,
                as_pct=True,
            )
        except Exception:
            exac_risks = np.zeros(len(df_scenario))

        # Ensure predictions and risks are iterable 1D arrays
        if isinstance(predictions, (float, int, np.floating)):
            predictions = np.array([predictions])
        else:
            predictions = np.asarray(predictions)

        if isinstance(exac_risks, (float, int, np.floating)):
            exac_risks = np.array([exac_risks])
        else:
            exac_risks = np.asarray(exac_risks)

        # Format trajectory points conforming to api_contract
        trajectory_points = []
        for t, pred_val, risk_val in zip(time_points, predictions, exac_risks):
            month_int = int(round(t)) if round(t) == t else round(t, 1)
            trajectory_points.append({
                "months_since_baseline": month_int,
                "predicted_fev1_liters": round(float(pred_val), 4),
                "exacerbation_risk_pct": round(float(risk_val), 1),
            })

        results[scenario_name] = trajectory_points

    return results
