from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

# Layer 1: Single Prediction
class PredictRequest(BaseModel):
    age_at_visit: float
    sex: str
    gold_stage_baseline: str
    smoking_status_at_visit: str
    pack_years: float
    activity_level_at_visit: str
    bmi: float
    months_since_baseline: float
    baseline_fev1_liters: float

class PredictResponse(BaseModel):
    predicted_fev1_liters: float
    model_used: str
    exacerbation_risk_pct: float

# Layer 2: Evolving Twin
class PatientSummary(BaseModel):
    patient_id: str
    summary: str

class TwinStateResponse(BaseModel):
    patient_id: str
    static: Dict[str, Any]
    current: Dict[str, Any]
    history: List[Dict[str, Any]]

class AddVisitRequest(BaseModel):
    visit_number: int
    months_since_baseline: float
    age_at_visit: float
    smoking_status_at_visit: str
    activity_level_at_visit: str
    fev1_liters: float
    fvc_liters: float
    fev1_fvc_ratio: float
    exacerbations_this_visit: int
    measurement_source: str

class CreatePatientRequest(BaseModel):
    patient_id: Optional[str] = None
    sex: str
    age_at_baseline: float
    gold_stage_baseline: Optional[str] = None
    smoking_status_baseline: str
    pack_years: float
    baseline_fev1_liters: float
    baseline_fvc_liters: float
    baseline_fev1_fvc_ratio: Optional[float] = None
    bmi: float
    activity_level_baseline: Optional[str] = "moderate"

class TwinHealthScoreResponse(BaseModel):
    patient_id: str
    health_score: float
    score_color: str
    status_label: str
    current_fev1: float
    baseline_fev1: float
    exacerbation_risk_pct: float
    annual_decline_rate_ml: float
    years_until_gold_iv: Optional[float]
    years_until_gold_iv_display: str
    grades: Dict[str, str]
    clinical_notes: str

class CohortPercentileResponse(BaseModel):
    patient_id: Optional[str] = None
    fev1: float
    percentile: float
    cohort_size: int
    rank: int
    placement_banner: str
    summary: str

# Layer 3: Simulation & Models
class SimulateRequest(BaseModel):
    patient_id: str
    horizon_months: int
    step_months: int
    scenarios: List[str]

class TrajectoryPoint(BaseModel):
    months_since_baseline: Union[int, float]
    predicted_fev1_liters: float
    exacerbation_risk_pct: float

class SimulateResponse(BaseModel):
    trajectories: Dict[str, List[TrajectoryPoint]]

class ModelComparisonResponse(BaseModel):
    rf_metrics: Dict[str, float]
    xgb_metrics: Dict[str, float]
    feature_importances: Dict[str, float]
    rf_feature_importances: Optional[Dict[str, float]] = None
    xgb_feature_importances: Optional[Dict[str, float]] = None

# Phase 1: Gemini Narrative Layer
class ExplainResponse(BaseModel):
    summary_bullets: List[str]
    risk_rationale: str

class TwinChatRequest(BaseModel):
    question: str

class TwinChatResponse(BaseModel):
    answer: str
