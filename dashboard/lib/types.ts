export interface PredictRequest {
  age_at_visit: number;
  sex: string;
  gold_stage_baseline: string;
  smoking_status_at_visit: string;
  pack_years: number;
  activity_level_at_visit: string;
  bmi: number;
  months_since_baseline: number;
  baseline_fev1_liters: number;
}

export interface PredictResponse {
  predicted_fev1_liters: number;
  model_used: string;
  exacerbation_risk_pct: number;
}

export interface PatientSummary {
  patient_id: string;
  summary: string;
}

export interface TwinStateResponse {
  patient_id: string;
  static: Record<string, any>;
  current: Record<string, any>;
  history: Array<Record<string, any>>;
}

export interface AddVisitRequest {
  visit_number: number;
  months_since_baseline: number;
  age_at_visit: number;
  smoking_status_at_visit: string;
  activity_level_at_visit: string;
  fev1_liters: number;
  fvc_liters: number;
  fev1_fvc_ratio: number;
  exacerbations_this_visit: number;
  measurement_source: string;
}

export interface TrajectoryPoint {
  months_since_baseline: number;
  predicted_fev1_liters: number;
  exacerbation_risk_pct: number;
}

export interface SimulateRequest {
  patient_id: string;
  horizon_months: number;
  step_months: number;
  scenarios: string[];
}

export interface SimulateResponse {
  trajectories: Record<string, TrajectoryPoint[]>;
}

export interface ModelComparisonResponse {
  rf_metrics: {
    mae: number;
    rmse: number;
    r2: number;
  };
  xgb_metrics: {
    mae: number;
    rmse: number;
    r2: number;
  };
  feature_importances: Record<string, number>;
  rf_feature_importances?: Record<string, number>;
  xgb_feature_importances?: Record<string, number>;
}

export interface ExplainResponse {
  summary_bullets: string[];
  risk_rationale: string;
}

export interface TwinChatRequest {
  question: string;
}

export interface TwinChatResponse {
  answer: string;
}

