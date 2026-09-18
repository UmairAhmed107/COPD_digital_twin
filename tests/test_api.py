"""Integration tests for FastAPI endpoints in api/main.py.

Verifies:
- Layer 1: POST /predict with Random Forest and XGBoost, plus validation errors.
- Layer 2: GET /patients, GET /patients/{id}, POST /patients/{id}/visits, 404 handling, and validation errors.
- Layer 3: POST /simulate with multiple what-if scenarios and GET /models/comparison.
- Exact compliance with Pydantic schemas defined in api/schemas.py.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import PATIENT_DB, app, init_mock_db
from api.schemas import (
    ExplainResponse,
    ModelComparisonResponse,
    PatientSummary,
    PredictResponse,
    SimulateResponse,
    TwinChatResponse,
    TwinStateResponse,
)


@pytest.fixture(autouse=True)
def reset_db_fixture():
    """Reset the mock database before every test to guarantee test isolation."""
    init_mock_db()
    yield
    init_mock_db()


@pytest.fixture
def client():
    """Provide a TestClient instance for API calls."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_predict_payload():
    """Valid 9-feature payload for /predict."""
    return {
        "age_at_visit": 65.0,
        "sex": "M",
        "gold_stage_baseline": "II",
        "smoking_status_at_visit": "former",
        "pack_years": 40.0,
        "activity_level_at_visit": "moderate",
        "bmi": 26.5,
        "months_since_baseline": 12.0,
        "baseline_fev1_liters": 2.10,
    }


def test_root_endpoint(client):
    """Verify root / returns online status and patient count."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["loaded_patients"] > 0


# =====================================================================
# Layer 1: /predict tests
# =====================================================================

def test_predict_random_forest(client, sample_predict_payload):
    """Verify /predict with default Random Forest model."""
    response = client.post("/predict", json=sample_predict_payload)
    assert response.status_code == 200
    data = response.json()

    # Validate against PredictResponse schema
    parsed = PredictResponse(**data)
    assert parsed.model_used == "random_forest"
    assert 0.5 <= parsed.predicted_fev1_liters <= 5.0
    assert 0.0 <= parsed.exacerbation_risk_pct <= 100.0


def test_predict_xgboost(client, sample_predict_payload):
    """Verify /predict with XGBoost via query parameter."""
    response = client.post("/predict?model_type=xgboost", json=sample_predict_payload)
    assert response.status_code == 200
    data = response.json()

    parsed = PredictResponse(**data)
    assert parsed.model_used == "xgboost"
    assert 0.5 <= parsed.predicted_fev1_liters <= 5.0
    assert 0.0 <= parsed.exacerbation_risk_pct <= 100.0


def test_predict_validation_error(client):
    """Verify /predict returns 422 when required features are missing."""
    incomplete_payload = {"age_at_visit": 65.0, "sex": "M"}
    response = client.post("/predict", json=incomplete_payload)
    assert response.status_code == 422


# =====================================================================
# Layer 2: /patients, /patients/{id}, /patients/{id}/visits tests
# =====================================================================

def test_list_patients(client):
    """Verify GET /patients returns a list of PatientSummary records."""
    response = client.get("/patients")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    first = data[0]
    parsed = PatientSummary(**first)
    assert parsed.patient_id == "P0001"
    assert "GOLD" in parsed.summary
    assert "visits" in parsed.summary


def test_get_patient_success(client):
    """Verify GET /patients/{id} returns full TwinStateResponse."""
    response = client.get("/patients/P0001")
    assert response.status_code == 200
    data = response.json()

    parsed = TwinStateResponse(**data)
    assert parsed.patient_id == "P0001"
    assert "sex" in parsed.static
    assert "months_since_baseline" in parsed.current
    assert len(parsed.history) >= 1


def test_get_patient_not_found(client):
    """Verify GET /patients/{id} returns 404 for unknown patient."""
    response = client.get("/patients/UNKNOWN_PATIENT_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_add_visit_success(client):
    """Verify POST /patients/{id}/visits appends observation and updates twin state."""
    # Get initial visit count
    init_res = client.get("/patients/P0001")
    initial_visits = len(init_res.json()["history"])

    new_visit_payload = {
        "visit_number": initial_visits + 1,
        "months_since_baseline": 36.0,
        "age_at_visit": 68.0,
        "smoking_status_at_visit": "former",
        "activity_level_at_visit": "high",
        "fev1_liters": 1.75,
        "fvc_liters": 2.95,
        "fev1_fvc_ratio": 0.59,
        "exacerbations_this_visit": 0,
        "measurement_source": "clinic",
    }

    response = client.post("/patients/P0001/visits", json=new_visit_payload)
    assert response.status_code == 200
    data = response.json()

    parsed = TwinStateResponse(**data)
    assert len(parsed.history) == initial_visits + 1
    assert parsed.current["visit_number"] == initial_visits + 1
    assert parsed.current["activity_level_at_visit"] == "high"
    assert parsed.current["fev1_liters"] == 1.75


def test_add_visit_patient_not_found(client):
    """Verify POST /patients/{id}/visits returns 404 for nonexistent patient."""
    dummy_visit = {
        "visit_number": 2,
        "months_since_baseline": 6.0,
        "age_at_visit": 66.0,
        "smoking_status_at_visit": "former",
        "activity_level_at_visit": "low",
        "fev1_liters": 1.5,
        "fvc_liters": 2.5,
        "fev1_fvc_ratio": 0.6,
        "exacerbations_this_visit": 0,
        "measurement_source": "clinic",
    }
    response = client.post("/patients/NONEXISTENT_PID/visits", json=dummy_visit)
    assert response.status_code == 404


def test_add_visit_validation_error(client):
    """Verify POST /patients/{id}/visits returns 422 on invalid schema."""
    response = client.post("/patients/P0001/visits", json={"visit_number": 2})
    assert response.status_code == 422


# =====================================================================
# Layer 3: /simulate and /models/comparison tests
# =====================================================================

def test_simulate_future_scenarios(client):
    """Verify POST /simulate returns future projections matching SimulateResponse."""
    payload = {
        "patient_id": "P0001",
        "horizon_months": 24,
        "step_months": 6,
        "scenarios": ["baseline", "smoking_cessation", "increased_activity"],
    }
    response = client.post("/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    parsed = SimulateResponse(**data)
    assert "baseline" in parsed.trajectories
    assert "smoking_cessation" in parsed.trajectories
    assert "increased_activity" in parsed.trajectories

    baseline_points = parsed.trajectories["baseline"]
    assert len(baseline_points) == 5  # 0, 6, 12, 18, 24 months

    for pt in baseline_points:
        assert isinstance(pt.months_since_baseline, int)
        assert 0.5 <= pt.predicted_fev1_liters <= 5.0
        assert isinstance(pt.exacerbation_risk_pct, float)
        assert 0.0 <= pt.exacerbation_risk_pct <= 100.0


def test_simulate_future_xgboost(client):
    """Verify POST /simulate supports model_type='xgboost' query parameter."""
    payload = {
        "patient_id": "P0001",
        "horizon_months": 12,
        "step_months": 6,
        "scenarios": ["baseline"],
    }
    response = client.post("/simulate?model_type=xgboost", json=payload)
    assert response.status_code == 200
    parsed = SimulateResponse(**response.json())
    assert len(parsed.trajectories["baseline"]) == 3  # 0, 6, 12 months


def test_simulate_patient_not_found(client):
    """Verify POST /simulate returns 404 for nonexistent patient."""
    payload = {
        "patient_id": "MISSING_PID",
        "horizon_months": 12,
        "step_months": 6,
        "scenarios": ["baseline"],
    }
    response = client.post("/simulate", json=payload)
    assert response.status_code == 404


def test_models_comparison(client):
    """Verify GET /models/comparison returns valid ModelComparisonResponse."""
    response = client.get("/models/comparison")
    assert response.status_code == 200
    data = response.json()

    parsed = ModelComparisonResponse(**data)
    for metric in ["mae", "rmse", "r2"]:
        assert metric in parsed.rf_metrics
        assert metric in parsed.xgb_metrics
        assert isinstance(parsed.rf_metrics[metric], float)
        assert isinstance(parsed.xgb_metrics[metric], float)

    assert len(parsed.feature_importances) > 0


def test_models_comparison_xgb_feature_importances(client):
    """Verify GET /models/comparison?feature_importance_model=xgb."""
    response = client.get("/models/comparison?feature_importance_model=xgb")
    assert response.status_code == 200
    data = response.json()
    parsed = ModelComparisonResponse(**data)
    assert len(parsed.feature_importances) > 0


# =====================================================================
# Phase 1: Gemini Narrative Layer Tests
# =====================================================================

def test_explain_endpoint_success(client, monkeypatch):
    """Verify POST /twins/{patient_id}/explain returns 3-bullet clinical summary and risk rationale."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    mock_explain_payload = {
        "summary_bullets": [
            "Patient demonstrates steady FEV1 decline from baseline 1.85L to 1.75L over 36 months.",
            "Key risk drivers include 35 pack-year smoking history and moderate baseline obstruction.",
            "Simulated trajectory projects smoking cessation preserves 0.15L FEV1 over 24 months."
        ],
        "risk_rationale": "Patient P0001 exhibits GOLD Stage II moderate obstruction with significant intervention sensitivity."
    }

    with patch("api.main.genai.Client") as mock_genai_client:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_explain_payload)
        mock_response.parsed = None
        mock_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_instance

        # Test primary route
        response = client.post("/twins/P0001/explain")
        assert response.status_code == 200
        data = response.json()

        parsed = ExplainResponse(**data)
        assert len(parsed.summary_bullets) == 3
        assert parsed.summary_bullets[0].startswith("Patient demonstrates")
        assert "GOLD Stage II" in parsed.risk_rationale

        # Verify call arguments passed to generate_content
        mock_instance.models.generate_content.assert_called_once()
        _, kwargs = mock_instance.models.generate_content.call_args
        assert "digital twin" in kwargs["config"].system_instruction.lower()

        # Test alias route /patients/{id}/explain
        mock_instance.models.generate_content.reset_mock()
        alias_res = client.post("/patients/P0001/explain")
        assert alias_res.status_code == 200
        assert len(alias_res.json()["summary_bullets"]) == 3


def test_explain_patient_not_found(client, monkeypatch):
    """Verify POST /twins/{patient_id}/explain returns 404 for missing patient."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")
    response = client.post("/twins/NONEXISTENT_P9999/explain")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_explain_missing_api_key(client, monkeypatch):
    """Verify POST /twins/{patient_id}/explain returns 503 when GEMINI_API_KEY is not configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = client.post("/twins/P0001/explain")
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_twin_chat_success(client, monkeypatch):
    """Verify POST /twins/{patient_id}/chat returns grounded clinical response."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    with patch("api.main.genai.Client") as mock_genai_client:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Based on the digital twin's 36-month trajectory, physical activity intervention slows FEV1 degradation significantly."
        mock_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_instance

        payload = {"question": "What is the benefit of increased physical activity?"}
        response = client.post("/twins/P0001/chat", json=payload)
        assert response.status_code == 200
        data = response.json()

        parsed = TwinChatResponse(**data)
        assert "FEV1 degradation" in parsed.answer


def test_explain_rate_limit_fallback(client, monkeypatch):
    """Verify POST /twins/{patient_id}/explain returns graceful fallback on Gemini API rate limit or error."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    with patch("api.main.genai.Client") as mock_genai_client:
        mock_instance = MagicMock()
        # Simulate 429 / ResourceExhausted exception
        mock_instance.models.generate_content.side_effect = Exception("429 Resource has been exhausted (e.g. check quota).")
        mock_genai_client.return_value = mock_instance

        response = client.post("/twins/P0001/explain")
        assert response.status_code == 200
        data = response.json()

        parsed = ExplainResponse(**data)
        assert len(parsed.summary_bullets) == 3
        assert "rate limits" in parsed.risk_rationale.lower()
        assert "P0001" in parsed.summary_bullets[0]


