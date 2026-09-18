"""Tests for SQLite persistence, patient onboarding (POST /patients),
Twin Health Score (GET /patients/{id}/health-score), and cohort percentile ranking (GET /cohort/percentile).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.database import PatientRecord, SessionLocal, VisitRecord, init_db
from api.main import app, init_mock_db
from api.schemas import (
    CohortPercentileResponse,
    CreatePatientRequest,
    TwinHealthScoreResponse,
    TwinStateResponse,
)


def cleanup_test_patients():
    with SessionLocal() as db:
        db.query(VisitRecord).filter(
            (VisitRecord.patient_id.like("P9%")) | (VisitRecord.patient_id > "P0100")
        ).delete(synchronize_session=False)
        db.query(PatientRecord).filter(
            (PatientRecord.patient_id.like("P9%")) | (PatientRecord.patient_id > "P0100")
        ).delete(synchronize_session=False)
        db.commit()


@pytest.fixture(autouse=True)
def reset_db_fixture():
    """Reset database before and after each test."""
    cleanup_test_patients()
    init_mock_db()
    yield
    cleanup_test_patients()
    init_mock_db()


@pytest.fixture
def client():
    """TestClient instance for API tests."""
    with TestClient(app) as test_client:
        yield test_client


def test_sqlite_persistence_preseeded():
    """Verify that the SQLite database is pre-seeded with synthetic patients."""
    with SessionLocal() as db:
        patient_count = db.query(PatientRecord).count()
        assert patient_count > 0, "Database should be pre-seeded with synthetic cohort"

        p1 = db.query(PatientRecord).filter_by(patient_id="P0001").first()
        assert p1 is not None
        assert p1.sex in ("M", "F")
        assert len(p1.visits) >= 1


def test_create_patient_success(client):
    """Verify POST /patients creates a new digital twin and persists to SQLite."""
    payload = {
        "patient_id": "P9999",
        "sex": "F",
        "age_at_baseline": 62.0,
        "gold_stage_baseline": "II (Moderate)",
        "smoking_status_baseline": "former",
        "pack_years": 25.0,
        "baseline_fev1_liters": 1.75,
        "baseline_fvc_liters": 2.90,
        "baseline_fev1_fvc_ratio": 0.60,
        "bmi": 24.5,
        "activity_level_baseline": "moderate",
    }

    response = client.post("/patients", json=payload)
    assert response.status_code == 201
    data = response.json()

    parsed = TwinStateResponse(**data)
    assert parsed.patient_id == "P9999"
    assert parsed.static["sex"] == "F"
    assert parsed.static["age_at_baseline"] == 62.0
    assert parsed.current["fev1_liters"] == 1.75
    assert len(parsed.history) == 1

    # Verify directly in SQLite
    with SessionLocal() as db:
        p_rec = db.query(PatientRecord).filter_by(patient_id="P9999").first()
        assert p_rec is not None
        assert p_rec.baseline_fev1_liters == 1.75
        assert len(p_rec.visits) == 1
        assert p_rec.visits[0].visit_number == 1


def test_create_patient_auto_id_and_inference(client):
    """Verify POST /patients auto-generates ID and auto-infers GOLD stage and ratio."""
    payload = {
        "sex": "M",
        "age_at_baseline": 55.0,
        "smoking_status_baseline": "current",
        "pack_years": 30.0,
        "baseline_fev1_liters": 2.80,
        "baseline_fvc_liters": 4.00,
        "bmi": 27.0,
    }

    response = client.post("/patients", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["patient_id"].startswith("P")
    assert data["static"]["gold_stage_baseline"] == "I (Mild)"
    assert data["static"]["baseline_fev1_fvc_ratio"] == 0.70


def test_create_patient_duplicate_id_fails(client):
    """Verify POST /patients returns 400 when attempting to create existing ID."""
    payload = {
        "patient_id": "P0001",
        "sex": "M",
        "age_at_baseline": 65.0,
        "smoking_status_baseline": "former",
        "pack_years": 35.0,
        "baseline_fev1_liters": 1.85,
        "baseline_fvc_liters": 3.10,
        "bmi": 26.0,
    }
    response = client.post("/patients", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_get_patient_health_score_success(client):
    """Verify GET /patients/{id}/health-score computes composite score, countdown, and grades."""
    response = client.get("/patients/P0001/health-score")
    assert response.status_code == 200
    data = response.json()

    parsed = TwinHealthScoreResponse(**data)
    assert parsed.patient_id == "P0001"
    assert 0.0 <= parsed.health_score <= 100.0
    assert parsed.score_color in ("green", "amber", "red")
    assert parsed.status_label != ""
    assert parsed.current_fev1 > 0
    assert parsed.baseline_fev1 > 0
    assert 0.0 <= parsed.exacerbation_risk_pct <= 100.0

    # Grades validation
    grades = parsed.grades
    assert "lung_function" in grades and grades["lung_function"] in ("A", "B", "C", "D", "F")
    assert "decline_rate" in grades and grades["decline_rate"] in ("A", "B", "C", "D", "F")
    assert "risk_trend" in grades and grades["risk_trend"] in ("A", "B", "C", "D", "F")

    # Milestone countdown
    assert parsed.years_until_gold_iv is not None or "Reached" in parsed.years_until_gold_iv_display
    assert "Years" in parsed.years_until_gold_iv_display or "Reached" in parsed.years_until_gold_iv_display


def test_get_patient_health_score_not_found(client):
    """Verify GET /patients/{id}/health-score returns 404 for unknown patient."""
    response = client.get("/patients/NONEXISTENT_PATIENT/health-score")
    assert response.status_code == 404


def test_cohort_percentile_by_patient_id(client):
    """Verify GET /cohort/percentile ranks patient against cohort peers."""
    response = client.get("/cohort/percentile?patient_id=P0001")
    assert response.status_code == 200
    data = response.json()

    parsed = CohortPercentileResponse(**data)
    assert parsed.patient_id == "P0001"
    assert 0.0 <= parsed.percentile <= 100.0
    assert parsed.cohort_size >= 1
    assert parsed.rank >= 1
    assert "cohort" in parsed.placement_banner.lower()
    assert "percentile" in parsed.summary.lower()


def test_cohort_percentile_by_fev1_value(client):
    """Verify GET /cohort/percentile ranks a direct FEV1 value."""
    response = client.get("/cohort/percentile?fev1=1.20")
    assert response.status_code == 200
    data = response.json()

    parsed = CohortPercentileResponse(**data)
    assert parsed.fev1 == 1.20
    assert 0.0 <= parsed.percentile <= 100.0
    assert "Worst" in parsed.placement_banner or "Top" in parsed.placement_banner


def test_cohort_percentile_missing_params(client):
    """Verify GET /cohort/percentile returns 400 when missing query parameters."""
    response = client.get("/cohort/percentile")
    assert response.status_code == 400
