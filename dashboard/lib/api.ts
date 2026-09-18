import {
  AddVisitRequest,
  ExplainResponse,
  ModelComparisonResponse,
  PatientSummary,
  PredictRequest,
  PredictResponse,
  SimulateRequest,
  SimulateResponse,
  TwinChatResponse,
  TwinStateResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === "string" 
          ? errorJson.detail 
          : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Keep status text if not json
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function checkApiHealth(): Promise<{ status: string; loaded_patients?: number }> {
  const res = await fetch(`${API_BASE_URL}/`, { cache: "no-store" });
  return handleResponse(res);
}

export async function predictFEV1(
  data: PredictRequest,
  modelType: "random_forest" | "xgboost" = "random_forest"
): Promise<PredictResponse> {
  const res = await fetch(`${API_BASE_URL}/predict?model_type=${modelType}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<PredictResponse>(res);
}

export async function getPatients(): Promise<PatientSummary[]> {
  const res = await fetch(`${API_BASE_URL}/patients`, { cache: "no-store" });
  return handleResponse<PatientSummary[]>(res);
}

export async function getPatient(patientId: string): Promise<TwinStateResponse> {
  const res = await fetch(`${API_BASE_URL}/patients/${encodeURIComponent(patientId)}`, {
    cache: "no-store",
  });
  return handleResponse<TwinStateResponse>(res);
}

export async function addPatientVisit(
  patientId: string,
  visit: AddVisitRequest
): Promise<TwinStateResponse> {
  const res = await fetch(`${API_BASE_URL}/patients/${encodeURIComponent(patientId)}/visits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(visit),
  });
  return handleResponse<TwinStateResponse>(res);
}

export async function simulateFuture(
  params: SimulateRequest,
  modelType: "random_forest" | "xgboost" = "random_forest"
): Promise<SimulateResponse> {
  const res = await fetch(`${API_BASE_URL}/simulate?model_type=${modelType}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse<SimulateResponse>(res);
}

export async function getModelComparison(
  featureImportanceModel: "rf" | "xgb" = "rf"
): Promise<ModelComparisonResponse> {
  const res = await fetch(
    `${API_BASE_URL}/models/comparison?feature_importance_model=${featureImportanceModel}`,
    { cache: "no-store" }
  );
  return handleResponse<ModelComparisonResponse>(res);
}

export async function getTwinExplanation(patientId: string): Promise<ExplainResponse> {
  const res = await fetch(`${API_BASE_URL}/twins/${encodeURIComponent(patientId)}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return handleResponse<ExplainResponse>(res);
}

export async function askTwinQuestion(
  patientId: string,
  question: string
): Promise<TwinChatResponse> {
  const res = await fetch(`${API_BASE_URL}/twins/${encodeURIComponent(patientId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return handleResponse<TwinChatResponse>(res);
}

