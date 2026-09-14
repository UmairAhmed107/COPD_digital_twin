"""FastAPI application for COPD Digital Twin API v2.

Implements endpoints across all three project demo layers:
- Layer 1: Single patient FEV1 prediction (`/predict`)
- Layer 2: Evolving digital twin patient picker and visit tracker (`/patients`, `/patients/{id}`, `/patients/{id}/visits`)
- Layer 3: Trajectory simulation under what-if scenarios (`/simulate`) and model comparison table (`/models/comparison`)
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from .schemas import (
    AddVisitRequest,
    ModelComparisonResponse,
    PatientSummary,
    PredictRequest,
    PredictResponse,
    SimulateRequest,
    SimulateResponse,
    TwinStateResponse,
)

try:
    from src.evaluation import get_model_comparison_response
    from src.model import predict_fev1 as model_predict_fev1
    from src.simulator import simulate_trajectory
    from src.twin_state import TwinState
except ImportError:
    from evaluation import get_model_comparison_response
    from model import predict_fev1 as model_predict_fev1
    from simulator import simulate_trajectory
    from twin_state import TwinState

# In-memory mock database of patient digital twins: patient_id -> TwinState
PATIENT_DB: Dict[str, TwinState] = {}
RAW_DATA_PATH = Path("data/raw/copd_synthetic_longitudinal.csv")


def init_mock_db(
    data_source: Optional[Union[str, Path, pd.DataFrame]] = None,
    limit: Optional[int] = None,
) -> None:
    """Populate the in-memory mock database with TwinState instances.

    Loads from a given DataFrame or CSV path (defaulting to RAW_DATA_PATH).
    If no source is found, seeds minimal synthetic demo patients.
    """
    global PATIENT_DB
    PATIENT_DB.clear()

    source_df = None
    if isinstance(data_source, pd.DataFrame):
        source_df = data_source
    else:
        path = Path(data_source) if data_source else RAW_DATA_PATH
        if path.exists():
            source_df = pd.read_csv(path)

    if source_df is not None and not source_df.empty:
        grouped = source_df.groupby("patient_id", sort=False)
        count = 0
        for pid, p_df in grouped:
            PATIENT_DB[str(pid)] = TwinState.from_dataframe(p_df)
            count += 1
            if limit is not None and count >= limit:
                break
    else:
        # Minimal fallback patient if dataset not present
        sample_static = {
            "patient_id": "P0001",
            "sex": "M",
            "age_at_baseline": 65.0,
            "gold_stage_baseline": "II",
            "smoking_status_baseline": "former",
            "pack_years": 35.0,
            "baseline_fev1_liters": 1.85,
            "baseline_fvc_liters": 3.10,
            "baseline_fev1_fvc_ratio": 0.60,
            "bmi": 26.2,
        }
        sample_visit = {
            "patient_id": "P0001",
            "visit_number": 1,
            "months_since_baseline": 0.0,
            "age_at_visit": 65.0,
            "smoking_status_at_visit": "former",
            "activity_level_at_visit": "moderate",
            "fev1_liters": 1.85,
            "fvc_liters": 3.10,
            "fev1_fvc_ratio": 0.60,
            "exacerbations_this_visit": 0,
            "measurement_source": "clinic",
        }
        PATIENT_DB["P0001"] = TwinState(static_data=sample_static, initial_visit=sample_visit)


# Automatically initialize patient DB on module import
init_mock_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure mock DB is initialized when API starts."""
    if not PATIENT_DB:
        init_mock_db()
    yield


app = FastAPI(
    title="COPD Digital Twin API v2",
    description="Backend API powering the COPD Digital Twin clinical dashboard",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for Next.js dashboard development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health and service info check."""
    return {
        "status": "online",
        "service": "COPD Digital Twin API v2",
        "loaded_patients": len(PATIENT_DB),
    }


# =====================================================================
# Layer 1: Single Patient Prediction
# =====================================================================

@app.post("/predict", response_model=PredictResponse)
def predict_fev1(
    request: PredictRequest,
    model_type: str = Query(
        default="random_forest",
        description="Regression model to use: 'random_forest' (or 'rf') or 'xgboost' (or 'xgb')",
    ),
):
    """Predict lung function (`fev1_liters`) for a given set of patient characteristics."""
    try:
        norm_type = "xgboost" if model_type.lower().strip() in ("xgb", "xgboost") else "random_forest"
        prediction = model_predict_fev1(request.model_dump(), model_type=norm_type)
        return PredictResponse(
            predicted_fev1_liters=round(float(prediction), 4),
            model_used=norm_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}")


# =====================================================================
# Layer 2: Evolving Digital Twin Patient Records
# =====================================================================

@app.get("/patients", response_model=List[PatientSummary])
def list_patients():
    """List available synthetic patients with descriptive summaries for the patient picker."""
    summaries: List[PatientSummary] = []
    for pid, twin in PATIENT_DB.items():
        sex = twin.static.get("sex", "Unknown")
        age = int(twin.static.get("age_at_baseline", twin.current.get("age_at_visit", 0)))
        gold = twin.static.get("gold_stage_baseline", "Unknown")
        smoking = twin.current.get("smoking_status_at_visit", "unknown").capitalize()
        num_visits = len(twin.history)
        summary_str = f"{sex}, Age {age}, GOLD {gold}, {smoking} ({num_visits} visits)"
        summaries.append(PatientSummary(patient_id=pid, summary=summary_str))
    return summaries


@app.get("/patients/{patient_id}", response_model=TwinStateResponse)
def get_patient(patient_id: str):
    """Retrieve full digital twin state including static fields, current state, and visit history."""
    twin = PATIENT_DB.get(patient_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
    return TwinStateResponse(**twin.to_dict())


@app.post("/patients/{patient_id}/visits", response_model=TwinStateResponse)
def add_visit(patient_id: str, visit: AddVisitRequest):
    """Append a newly observed clinical visit to the patient's record and update twin state."""
    twin = PATIENT_DB.get(patient_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")

    visit_data = visit.model_dump()
    twin.add_visit(visit_data)
    return TwinStateResponse(**twin.to_dict())


# =====================================================================
# Layer 3: Future Simulation & Model Comparison
# =====================================================================

@app.post("/simulate", response_model=SimulateResponse)
def simulate_future(
    request: SimulateRequest,
    model_type: str = Query(
        default="random_forest",
        description="Regression model for simulation: 'random_forest' or 'xgboost'",
    ),
):
    """Simulate future lung function trajectories from current twin state across what-if scenarios."""
    twin = PATIENT_DB.get(request.patient_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{request.patient_id}' not found.")

    try:
        trajectories = simulate_trajectory(
            twin_state=twin,
            horizon_months=request.horizon_months,
            step_months=request.step_months,
            scenario_modifications=request.scenarios,
            model_type=model_type,
        )
        formatted_trajectories = {
            scenario: [
                {
                    "months_since_baseline": int(round(pt["months_since_baseline"])),
                    "predicted_fev1_liters": pt["predicted_fev1_liters"],
                }
                for pt in pts
            ]
            for scenario, pts in trajectories.items()
        }
        return SimulateResponse(trajectories=formatted_trajectories)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation error: {exc}")


@app.get("/models/comparison", response_model=ModelComparisonResponse)
def compare_models(
    feature_importance_model: str = Query(
        default="rf",
        description="Model to populate primary feature importances: 'rf' or 'xgb'",
    ),
):
    """Return model comparison performance metrics (MAE, RMSE, R²) and feature importances."""
    try:
        return get_model_comparison_response(feature_importance_model=feature_importance_model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model comparison: {exc}")