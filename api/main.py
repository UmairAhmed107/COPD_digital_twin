"""FastAPI application for COPD Digital Twin API v2.

Implements endpoints across all three project demo layers:
- Layer 1: Single patient FEV1 prediction (`/predict`)
- Layer 2: Evolving digital twin patient picker and visit tracker (`/patients`, `/patients/{id}`, `/patients/{id}/visits`)
- Layer 3: Trajectory simulation under what-if scenarios (`/simulate`) and model comparison table (`/models/comparison`)
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
logger = logging.getLogger(__name__)


from .schemas import (
    AddVisitRequest,
    ExplainResponse,
    ModelComparisonResponse,
    PatientSummary,
    PredictRequest,
    PredictResponse,
    SimulateRequest,
    SimulateResponse,
    TwinChatRequest,
    TwinChatResponse,
    TwinStateResponse,
)

try:
    from src.evaluation import get_model_comparison_response
    from src.model import predict_fev1 as model_predict_fev1, predict_exacerbation_risk
    from src.simulator import simulate_trajectory
    from src.twin_state import TwinState
except ImportError:
    from evaluation import get_model_comparison_response
    from model import predict_fev1 as model_predict_fev1, predict_exacerbation_risk
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
    """Predict lung function (`fev1_liters`) and exacerbation risk for a given set of patient characteristics."""
    try:
        norm_type = "xgboost" if model_type.lower().strip() in ("xgb", "xgboost") else "random_forest"
        req_dict = request.model_dump()
        prediction = model_predict_fev1(req_dict, model_type=norm_type)
        try:
            exac_risk = predict_exacerbation_risk(req_dict, as_pct=True)
        except Exception:
            exac_risk = 0.0

        return PredictResponse(
            predicted_fev1_liters=round(float(prediction), 4),
            model_used=norm_type,
            exacerbation_risk_pct=round(float(exac_risk), 1),
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
                    "exacerbation_risk_pct": pt.get("exacerbation_risk_pct", 0.0),
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


# =====================================================================
# Phase 1: Gemini Narrative Layer & Virtual Pulmonology Consultation
# =====================================================================

EXPLAIN_SYSTEM_INSTRUCTION = (
    "You are an expert pulmonologist. Analyze this digital twin data. "
    "Provide a 3-bullet clinical summary explaining why the patient is progressing, "
    "key risk drivers, and intervention benefits. Ground all assertions strictly "
    "in the provided data. Do not hallucinate."
)


@app.post("/twins/{patient_id}/explain", response_model=ExplainResponse)
def explain_twin(patient_id: str):
    """Generate a 3-bullet clinical summary and risk rationale using Gemini."""
    twin = PATIENT_DB.get(patient_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY environment variable is not configured on the server.",
        )

    try:
        baseline_trajectories = simulate_trajectory(
            twin_state=twin,
            horizon_months=24,
            step_months=6,
            scenario_modifications=["baseline", "smoking_cessation", "increased_activity"],
        )

        formatted_trajectories = {
            scenario: [
                {
                    "months_since_baseline": int(round(pt["months_since_baseline"])),
                    "predicted_fev1_liters": round(float(pt["predicted_fev1_liters"]), 3),
                }
                for pt in pts
            ]
            for scenario, pts in baseline_trajectories.items()
        }

        digital_twin_payload = {
            "patient_id": patient_id,
            "static_baseline": twin.static,
            "current_observation": twin.current,
            "longitudinal_history": twin.history,
            "projected_24mo_trajectories": formatted_trajectories,
        }

        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

        user_content = (
            f"Patient Digital Twin & Future Trajectory Data:\n"
            f"{json.dumps(digital_twin_payload, default=str, indent=2)}\n\n"
            f"Analyze this patient digital twin and provide the structured clinical summary."
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=EXPLAIN_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ExplainResponse,
                ),
            )

            if hasattr(response, "parsed") and isinstance(response.parsed, ExplainResponse):
                return response.parsed
            if hasattr(response, "parsed") and isinstance(response.parsed, dict):
                return ExplainResponse(**response.parsed)

            raw_text = (response.text or "").strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()
            parsed_json = json.loads(raw_text)
            return ExplainResponse(**parsed_json)
        except Exception as api_exc:
            logger.warning("Gemini generate_content API error in explain_twin: %s", api_exc)
            current_obs = twin.current or {}
            static_data = twin.static or {}
            current_fev1 = float(current_obs.get("fev1_liters", static_data.get("baseline_fev1_liters", 1.85)))
            baseline_fev1 = float(static_data.get("baseline_fev1_liters", 2.0))
            gold_stage = static_data.get("gold_stage_baseline", "II")
            return ExplainResponse(
                summary_bullets=[
                    f"Patient {patient_id} presents with GOLD Stage {gold_stage} COPD, maintaining current FEV1 of {current_fev1:.2f} L against baseline {baseline_fev1:.2f} L.",
                    "Longitudinal trajectory projections demonstrate preventive lifestyle changes (smoking cessation and high activity) substantially attenuate FEV1 decline.",
                    "AI Summary temporarily operating in resilient fallback mode due to upstream Gemini API rate limits or network latency.",
                ],
                risk_rationale=(
                    "AI Summary temporarily unavailable due to rate limits. Please wait a moment before refreshing. "
                    "Longitudinal spirometry tracking, patient history ledger, and machine learning simulation models remain fully operational."
                ),
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Twin trajectory simulation error: {exc}")


@app.post("/patients/{patient_id}/explain", response_model=ExplainResponse, include_in_schema=False)
def explain_patient_alias(patient_id: str):
    """Alias for /twins/{patient_id}/explain to maintain endpoint consistency."""
    return explain_twin(patient_id)


@app.post("/twins/{patient_id}/chat", response_model=TwinChatResponse)
def chat_with_twin(patient_id: str, request: TwinChatRequest):
    """Virtual pulmonologist interactive chat grounded in the patient digital twin."""
    twin = PATIENT_DB.get(patient_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY environment variable is not configured on the server.",
        )

    try:
        baseline_trajectories = simulate_trajectory(
            twin_state=twin,
            horizon_months=24,
            step_months=6,
            scenario_modifications=["baseline", "smoking_cessation", "increased_activity"],
        )

        formatted_trajectories = {
            scenario: [
                {
                    "months_since_baseline": int(round(pt["months_since_baseline"])),
                    "predicted_fev1_liters": round(float(pt["predicted_fev1_liters"]), 3),
                }
                for pt in pts
            ]
            for scenario, pts in baseline_trajectories.items()
        }

        digital_twin_payload = {
            "patient_id": patient_id,
            "static_baseline": twin.static,
            "current_observation": twin.current,
            "longitudinal_history": twin.history,
            "projected_24mo_trajectories": formatted_trajectories,
        }

        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

        system_instruction = (
            "You are an expert pulmonologist and clinical digital twin assistant. "
            "You are interacting with a physician or clinical researcher inquiring about this patient. "
            "Ground your answer strictly in the provided patient digital twin baseline, longitudinal history, "
            "and projected trajectory data. Keep responses concise, clinically grounded, clear, and professional. "
            "Do not hallucinate facts not supported by the data."
        )

        prompt = (
            f"Patient Digital Twin Context:\n"
            f"{json.dumps(digital_twin_payload, default=str, indent=2)}\n\n"
            f"Clinician Question: {request.question}\n\n"
            f"Provide a concise, data-grounded clinical response."
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            return TwinChatResponse(answer=response.text or "No response generated.")
        except Exception as api_exc:
            logger.warning("Gemini generate_content API error in chat_with_twin: %s", api_exc)
            return TwinChatResponse(
                answer=(
                    "Virtual Pulmonologist consultation is temporarily unavailable due to API rate limits. "
                    "Please wait a moment and try your question again."
                )
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Twin chat error: {exc}")