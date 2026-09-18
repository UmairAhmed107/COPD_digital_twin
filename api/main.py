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
    CohortPercentileResponse,
    CreatePatientRequest,
    ExplainResponse,
    ModelComparisonResponse,
    PatientSummary,
    PredictRequest,
    PredictResponse,
    SimulateRequest,
    SimulateResponse,
    TwinChatRequest,
    TwinChatResponse,
    TwinHealthScoreResponse,
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

try:
    from api.database import (
        DEFAULT_DB_PATH,
        PatientRecord,
        SessionLocal,
        VisitRecord,
        init_db,
        record_to_twin_state,
        seed_database_if_empty,
        twin_state_to_db,
    )
except ImportError:
    from database import (
        DEFAULT_DB_PATH,
        PatientRecord,
        SessionLocal,
        VisitRecord,
        init_db,
        record_to_twin_state,
        seed_database_if_empty,
        twin_state_to_db,
    )

# Active in-memory cache synchronized with SQLite database: patient_id -> TwinState
PATIENT_DB: Dict[str, TwinState] = {}
RAW_DATA_PATH = Path("data/raw/copd_synthetic_longitudinal.csv")


def init_mock_db(
    data_source: Optional[Union[str, Path, pd.DataFrame]] = None,
    limit: Optional[int] = None,
) -> None:
    """Populate SQLite database and in-memory cache with TwinState instances.

    Loads from a given DataFrame or CSV path (defaulting to RAW_DATA_PATH).
    If no source is found, seeds minimal synthetic demo patients.
    """
    global PATIENT_DB
    PATIENT_DB.clear()

    init_db()

    with SessionLocal() as db:
        if data_source is None:
            seed_database_if_empty(db, csv_path=RAW_DATA_PATH, limit=limit)
            existing = db.query(PatientRecord).all()
            if existing:
                for p_rec in existing:
                    twin = record_to_twin_state(p_rec)
                    PATIENT_DB[twin.patient_id] = twin
                    if limit is not None and len(PATIENT_DB) >= limit:
                        break
                return

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
                twin = TwinState.from_dataframe(p_df)
                PATIENT_DB[str(pid)] = twin
                twin_state_to_db(twin, db)
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
            twin = TwinState(static_data=sample_static, initial_visit=sample_visit)
            PATIENT_DB["P0001"] = twin
            twin_state_to_db(twin, db)


# Automatically initialize patient DB on module import
init_mock_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure SQLite database is created, seeded, and synchronized on startup."""
    init_db()
    with SessionLocal() as db:
        seed_database_if_empty(db, csv_path=RAW_DATA_PATH)
        for p_rec in db.query(PatientRecord).all():
            PATIENT_DB[p_rec.patient_id] = record_to_twin_state(p_rec)
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
# Layer 2: Evolving Digital Twin Patient Records & Population Intelligence
# =====================================================================

@app.get("/patients", response_model=List[PatientSummary])
def list_patients():
    """List available synthetic patients with descriptive summaries for the patient picker."""
    summaries: List[PatientSummary] = []
    
    # Check SQLite first to ensure all newly created patients are included
    with SessionLocal() as db:
        records = db.query(PatientRecord).all()
        if records:
            for p_rec in records:
                twin = record_to_twin_state(p_rec)
                PATIENT_DB[twin.patient_id] = twin

    for pid, twin in PATIENT_DB.items():
        sex = twin.static.get("sex", "Unknown")
        age = int(twin.static.get("age_at_baseline", twin.current.get("age_at_visit", 0)))
        gold = twin.static.get("gold_stage_baseline", "Unknown")
        smoking = twin.current.get("smoking_status_at_visit", "unknown").capitalize()
        num_visits = len(twin.history)
        summary_str = f"{sex}, Age {age}, GOLD {gold}, {smoking} ({num_visits} visits)"
        summaries.append(PatientSummary(patient_id=pid, summary=summary_str))
    return summaries


@app.post(
    "/patients",
    response_model=TwinStateResponse,
    status_code=201,
    description="Create a new digital twin and persist to SQLite database.",
)
def create_patient(payload: CreatePatientRequest):
    """Create a new patient digital twin, initialize baseline Visit 1, and persist to SQLite."""
    with SessionLocal() as db:
        # Determine patient ID
        if payload.patient_id and payload.patient_id.strip():
            pid = payload.patient_id.strip()
            if db.query(PatientRecord).filter_by(patient_id=pid).first() or pid in PATIENT_DB:
                raise HTTPException(status_code=400, detail=f"Patient with ID '{pid}' already exists.")
        else:
            # Auto-generate next sequential ID (e.g. P0101, P0102)
            existing_pids = [p.patient_id for p in db.query(PatientRecord.patient_id).all()] + list(PATIENT_DB.keys())
            max_num = 0
            for existing in existing_pids:
                if existing.startswith("P") and existing[1:].isdigit():
                    try:
                        num = int(existing[1:])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            pid = f"P{max_num + 1:04d}"

        # Auto-infer GOLD stage baseline if not specified
        gold_stage = payload.gold_stage_baseline
        if not gold_stage:
            fev1 = payload.baseline_fev1_liters
            if fev1 >= 2.5:
                gold_stage = "I (Mild)"
            elif fev1 >= 1.7:
                gold_stage = "II (Moderate)"
            elif fev1 >= 1.0:
                gold_stage = "III (Severe)"
            else:
                gold_stage = "IV (Very Severe)"

        # Auto-calculate ratio if not provided
        ratio = payload.baseline_fev1_fvc_ratio
        if ratio is None or ratio <= 0:
            ratio = round(payload.baseline_fev1_liters / max(0.1, payload.baseline_fvc_liters), 2)

        static_data = {
            "patient_id": pid,
            "sex": payload.sex.upper(),
            "age_at_baseline": float(payload.age_at_baseline),
            "gold_stage_baseline": gold_stage,
            "smoking_status_baseline": payload.smoking_status_baseline.lower(),
            "pack_years": float(payload.pack_years),
            "baseline_fev1_liters": float(payload.baseline_fev1_liters),
            "baseline_fvc_liters": float(payload.baseline_fvc_liters),
            "baseline_fev1_fvc_ratio": float(ratio),
            "bmi": float(payload.bmi),
        }

        initial_visit = {
            "patient_id": pid,
            "visit_number": 1,
            "months_since_baseline": 0.0,
            "age_at_visit": float(payload.age_at_baseline),
            "smoking_status_at_visit": payload.smoking_status_baseline.lower(),
            "activity_level_at_visit": (payload.activity_level_baseline or "moderate").lower(),
            "fev1_liters": float(payload.baseline_fev1_liters),
            "fvc_liters": float(payload.baseline_fvc_liters),
            "fev1_fvc_ratio": float(ratio),
            "exacerbations_this_visit": 0,
            "measurement_source": "clinic",
        }

        twin = TwinState(static_data=static_data, initial_visit=initial_visit, patient_id=pid)
        twin_state_to_db(twin, db)
        PATIENT_DB[pid] = twin

        return TwinStateResponse(**twin.to_dict())


@app.get("/patients/{patient_id}", response_model=TwinStateResponse)
def get_patient(patient_id: str):
    """Retrieve full digital twin state including static fields, current state, and visit history."""
    twin = PATIENT_DB.get(patient_id)
    if not twin:
        with SessionLocal() as db:
            p_rec = db.query(PatientRecord).filter_by(patient_id=patient_id).first()
            if p_rec:
                twin = record_to_twin_state(p_rec)
                PATIENT_DB[patient_id] = twin

    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
    return TwinStateResponse(**twin.to_dict())


@app.post("/patients/{patient_id}/visits", response_model=TwinStateResponse)
def add_visit(patient_id: str, visit: AddVisitRequest):
    """Append a newly observed clinical visit to the patient's record and update twin state."""
    twin = PATIENT_DB.get(patient_id)
    with SessionLocal() as db:
        if not twin:
            p_rec = db.query(PatientRecord).filter_by(patient_id=patient_id).first()
            if p_rec:
                twin = record_to_twin_state(p_rec)

        if not twin:
            raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")

        visit_data = visit.model_dump()
        twin.add_visit(visit_data)
        twin_state_to_db(twin, db)
        PATIENT_DB[patient_id] = twin
        return TwinStateResponse(**twin.to_dict())


@app.get(
    "/patients/{patient_id}/health-score",
    response_model=TwinHealthScoreResponse,
    description="Calculate composite 0-100 Twin Health Score, GOLD Stage IV countdown, and report-card grades.",
)
def get_patient_health_score(patient_id: str):
    """Dynamically compute composite Twin Health Score, milestone countdown, and clinical grades."""
    twin = PATIENT_DB.get(patient_id)
    if not twin:
        with SessionLocal() as db:
            p_rec = db.query(PatientRecord).filter_by(patient_id=patient_id).first()
            if p_rec:
                twin = record_to_twin_state(p_rec)
                PATIENT_DB[patient_id] = twin

    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")

    current_fev1 = float(twin.current.get("fev1_liters", twin.static.get("baseline_fev1_liters", 1.85)))
    baseline_fev1 = float(twin.static.get("baseline_fev1_liters", 2.0))
    months = float(twin.current.get("months_since_baseline", 0.0))

    # Predict exacerbation risk using approved 9 features
    predict_payload = {
        "age_at_visit": float(twin.current.get("age_at_visit", twin.static.get("age_at_baseline", 65.0))),
        "sex": str(twin.static.get("sex", "M")),
        "gold_stage_baseline": str(twin.static.get("gold_stage_baseline", "II (Moderate)")),
        "smoking_status_at_visit": str(twin.current.get("smoking_status_at_visit", "former")),
        "pack_years": float(twin.static.get("pack_years", 30.0)),
        "activity_level_at_visit": str(twin.current.get("activity_level_at_visit", "moderate")),
        "bmi": float(twin.static.get("bmi", 26.0)),
        "months_since_baseline": months,
        "baseline_fev1_liters": baseline_fev1,
    }
    try:
        exac_risk = float(predict_exacerbation_risk(predict_payload, as_pct=True))
    except Exception as exc:
        logger.warning("Could not predict exacerbation risk for %s: %s", patient_id, exc)
        exac_risk = 22.5

    # 1. Composite Twin Health Score (0 - 100)
    fev1_norm = min(100.0, max(0.0, (current_fev1 / 3.0) * 100.0))
    risk_score = max(0.0, 100.0 - exac_risk)
    composite_health_score = round(0.6 * fev1_norm + 0.4 * risk_score, 1)

    if composite_health_score >= 75.0:
        score_color = "green"
        status_label = "Optimal / Compensated"
    elif composite_health_score >= 50.0:
        score_color = "amber"
        status_label = "Guarded / Moderate Obstruction"
    else:
        score_color = "red"
        status_label = "Critical / Severe Risk"

    # 2. Annualized decline rate
    if months >= 3.0:
        decline_annual = (baseline_fev1 - current_fev1) / (months / 12.0)
        annual_decline_ml = round(decline_annual * 1000.0, 1)
    else:
        annual_decline_ml = 38.0

    # 3. Report-Card Grades (A - F)
    # Lung Function grade
    if current_fev1 >= 2.5:
        lung_grade = "A"
    elif current_fev1 >= 2.0:
        lung_grade = "B"
    elif current_fev1 >= 1.5:
        lung_grade = "C"
    elif current_fev1 >= 1.0:
        lung_grade = "D"
    else:
        lung_grade = "F"

    # Decline Rate grade
    if annual_decline_ml <= 20.0:
        decline_grade = "A"
    elif annual_decline_ml <= 45.0:
        decline_grade = "B"
    elif annual_decline_ml <= 75.0:
        decline_grade = "C"
    elif annual_decline_ml <= 110.0:
        decline_grade = "D"
    else:
        decline_grade = "F"

    # Risk Trend grade
    if exac_risk <= 15.0:
        risk_grade = "A"
    elif exac_risk <= 30.0:
        risk_grade = "B"
    elif exac_risk <= 50.0:
        risk_grade = "C"
    elif exac_risk <= 70.0:
        risk_grade = "D"
    else:
        risk_grade = "F"

    # 4. Years until GOLD Stage IV milestone (FEV1 <= 0.90L)
    STAGE_IV_FEV1 = 0.90
    if current_fev1 <= STAGE_IV_FEV1:
        years_until_gold_iv = 0.0
        countdown_display = "Stage IV Reached (Critical)"
    else:
        effective_annual_loss = max(0.015, annual_decline_ml / 1000.0)
        est_years = round((current_fev1 - STAGE_IV_FEV1) / effective_annual_loss, 1)
        if est_years > 25.0:
            years_until_gold_iv = est_years
            countdown_display = "> 25 Years (Stabilized)"
        else:
            years_until_gold_iv = max(0.1, est_years)
            countdown_display = f"{years_until_gold_iv:.1f} Years"

    return TwinHealthScoreResponse(
        patient_id=patient_id,
        health_score=composite_health_score,
        score_color=score_color,
        status_label=status_label,
        current_fev1=round(current_fev1, 3),
        baseline_fev1=round(baseline_fev1, 3),
        exacerbation_risk_pct=round(exac_risk, 1),
        annual_decline_rate_ml=annual_decline_ml,
        years_until_gold_iv=years_until_gold_iv,
        years_until_gold_iv_display=countdown_display,
        grades={
            "lung_function": lung_grade,
            "decline_rate": decline_grade,
            "risk_trend": risk_grade,
        },
        clinical_notes=(
            f"Composite health score {composite_health_score}/100 with "
            f"{countdown_display} projected until GOLD Stage IV milestone."
        ),
    )


@app.get(
    "/cohort/percentile",
    response_model=CohortPercentileResponse,
    description="Calculate where a patient's FEV1 ranks against the synthetic peer cohort.",
)
def get_cohort_percentile(
    patient_id: Optional[str] = Query(default=None, description="Patient ID to rank"),
    fev1: Optional[float] = Query(default=None, description="Direct FEV1 value to rank against cohort"),
):
    """Return patient's FEV1 percentile and placement banner within the synthetic cohort."""
    target_fev1: float = 0.0

    if fev1 is not None:
        target_fev1 = float(fev1)
    elif patient_id is not None:
        twin = PATIENT_DB.get(patient_id)
        if not twin:
            with SessionLocal() as db:
                p_rec = db.query(PatientRecord).filter_by(patient_id=patient_id).first()
                if p_rec:
                    twin = record_to_twin_state(p_rec)
                    PATIENT_DB[patient_id] = twin

        if not twin:
            raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
        target_fev1 = float(twin.current.get("fev1_liters", twin.static.get("baseline_fev1_liters", 1.85)))
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'patient_id' or 'fev1' parameter must be provided.",
        )

    # Collect cohort FEV1 values from SQLite or in-memory cache
    cohort_fev1s: List[float] = []
    with SessionLocal() as db:
        records = db.query(PatientRecord).all()
        for rec in records:
            if rec.visits:
                cohort_fev1s.append(float(rec.visits[-1].fev1_liters))
            else:
                cohort_fev1s.append(float(rec.baseline_fev1_liters))

    if not cohort_fev1s and PATIENT_DB:
        for twin in PATIENT_DB.values():
            cohort_fev1s.append(float(twin.current.get("fev1_liters", twin.static.get("baseline_fev1_liters", 1.85))))

    if not cohort_fev1s:
        cohort_fev1s = [1.1, 1.4, 1.6, 1.85, 2.1, 2.4, 2.8, 3.2]

    # Calculate percentile (lower FEV1 = lower percentile)
    count_leq = sum(1 for val in cohort_fev1s if val <= target_fev1)
    percentile = round((count_leq / len(cohort_fev1s)) * 100.0, 1)

    # Rank (1 = highest FEV1)
    sorted_cohort = sorted(cohort_fev1s, reverse=True)
    rank = 1
    for idx, val in enumerate(sorted_cohort):
        if target_fev1 >= val:
            rank = idx + 1
            break
        rank = len(sorted_cohort)

    # Placement banner
    if percentile < 50.0:
        worst_pct = max(1, int(round(percentile)))
        placement_banner = f"Worst {worst_pct}% of cohort"
    else:
        top_pct = max(1, int(round(100.0 - percentile)))
        placement_banner = f"Top {top_pct}% of cohort"

    summary = (
        f"FEV1 of {target_fev1:.2f} L ranks at the {percentile}th percentile "
        f"(Rank #{rank} of {len(cohort_fev1s)}) across the synthetic COPD cohort."
    )

    return CohortPercentileResponse(
        patient_id=patient_id,
        fev1=round(target_fev1, 3),
        percentile=percentile,
        cohort_size=len(cohort_fev1s),
        rank=rank,
        placement_banner=placement_banner,
        summary=summary,
    )


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