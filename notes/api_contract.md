# API Contract v2 — COPD Digital Twin

FastAPI backend, consumed by the Next.js/React dashboard. Keep responses
JSON, keep endpoints stateless except where noted.

## `POST /predict`
Layer 1 — single prediction from manually entered patient data.

Request body: the approved feature list (age_at_visit, sex,
gold_stage_baseline, smoking_status_at_visit, pack_years,
activity_level_at_visit, bmi, months_since_baseline, baseline_fev1_liters).

Response: `{ "predicted_fev1_liters": float, "model_used": "random_forest" | "xgboost" }`

## `GET /patients`
List available synthetic patients (id + short summary) for Layer 2's
patient picker.

## `GET /patients/{patient_id}`
Returns the patient's twin state: static fields, current fields, and full
visit history (for the trajectory chart).

## `POST /patients/{patient_id}/visits`
Layer 2 — "Add Visit". Body: the new visit's observed fields. Appends the
visit, updates the twin's current state, and returns the updated twin state
plus a fresh prediction.

## `POST /simulate`
Layer 3 — future/what-if simulation.

Request body:
```
{
  "patient_id": "P0001",
  "horizon_months": 36,
  "step_months": 6,
  "scenarios": ["baseline", "smoking_cessation", "increased_activity"]
}
```

Response: one trajectory array per scenario, each a list of
`{ "months_since_baseline": int, "predicted_fev1_liters": float }`.

## `GET /models/comparison`
Layer 3 — model comparison table. Returns MAE/RMSE/R² for RF and XGBoost
on the held-out test set, plus feature importances if available.
