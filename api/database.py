"""SQLAlchemy SQLite persistence layer for COPD Digital Twin.

Provides:
- PatientRecord and VisitRecord relational models.
- Database session factory and schema initialization.
- TwinState bidirectional serialization.
- Cohort pre-seeding from longitudinal CSV.
"""

import copy
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

import pandas as pd
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    relationship,
    sessionmaker,
)

try:
    from src.twin_state import STATIC_FIELDS, TwinState
except ImportError:
    from twin_state import STATIC_FIELDS, TwinState

logger = logging.getLogger(__name__)

# Configurable database path (defaults to data/copd_twins.db)
DEFAULT_DB_PATH = Path("data/copd_twins.db")
DB_PATH = Path(os.environ.get("COPD_DB_PATH", DEFAULT_DB_PATH))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""
    pass


class PatientRecord(Base):
    """SQLAlchemy model representing a patient's baseline digital twin identity."""

    __tablename__ = "patients"

    patient_id = Column(String, primary_key=True, index=True)
    sex = Column(String, nullable=False)
    age_at_baseline = Column(Float, nullable=False)
    gold_stage_baseline = Column(String, nullable=False)
    smoking_status_baseline = Column(String, nullable=False)
    pack_years = Column(Float, nullable=False)
    baseline_fev1_liters = Column(Float, nullable=False)
    baseline_fvc_liters = Column(Float, nullable=False)
    baseline_fev1_fvc_ratio = Column(Float, nullable=False)
    bmi = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    visits = relationship(
        "VisitRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="VisitRecord.visit_number",
    )


class VisitRecord(Base):
    """SQLAlchemy model representing a single longitudinal clinic or home visit."""

    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(
        String,
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_number = Column(Integer, nullable=False)
    months_since_baseline = Column(Float, nullable=False)
    age_at_visit = Column(Float, nullable=False)
    smoking_status_at_visit = Column(String, nullable=False)
    activity_level_at_visit = Column(String, nullable=False)
    fev1_liters = Column(Float, nullable=False)
    fvc_liters = Column(Float, nullable=False)
    fev1_fvc_ratio = Column(Float, nullable=False)
    exacerbations_this_visit = Column(Integer, default=0)
    measurement_source = Column(String, default="clinic")
    spo2_pct = Column(Float, nullable=True)
    cat_score = Column(Float, nullable=True)

    patient = relationship("PatientRecord", back_populates="visits")


def init_db(engine_to_use=None) -> None:
    """Create all database tables if they do not already exist."""
    target_engine = engine_to_use or engine
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding an isolated database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def record_to_twin_state(patient_rec: PatientRecord) -> TwinState:
    """Convert an SQLAlchemy PatientRecord and its associated visits into a TwinState instance."""
    static_data = {
        "patient_id": patient_rec.patient_id,
        "sex": patient_rec.sex,
        "age_at_baseline": float(patient_rec.age_at_baseline),
        "gold_stage_baseline": patient_rec.gold_stage_baseline,
        "smoking_status_baseline": patient_rec.smoking_status_baseline,
        "pack_years": float(patient_rec.pack_years),
        "baseline_fev1_liters": float(patient_rec.baseline_fev1_liters),
        "baseline_fvc_liters": float(patient_rec.baseline_fvc_liters),
        "baseline_fev1_fvc_ratio": float(patient_rec.baseline_fev1_fvc_ratio),
        "bmi": float(patient_rec.bmi),
    }

    history: List[Dict[str, Any]] = []
    for v in sorted(patient_rec.visits, key=lambda x: x.visit_number):
        v_dict = {
            "patient_id": patient_rec.patient_id,
            "visit_number": int(v.visit_number),
            "months_since_baseline": float(v.months_since_baseline),
            "age_at_visit": float(v.age_at_visit),
            "smoking_status_at_visit": v.smoking_status_at_visit,
            "activity_level_at_visit": v.activity_level_at_visit,
            "fev1_liters": float(v.fev1_liters),
            "fvc_liters": float(v.fvc_liters),
            "fev1_fvc_ratio": float(v.fev1_fvc_ratio),
            "exacerbations_this_visit": int(v.exacerbations_this_visit),
            "measurement_source": v.measurement_source or "clinic",
        }
        if v.spo2_pct is not None:
            v_dict["spo2_pct"] = float(v.spo2_pct)
        if v.cat_score is not None:
            v_dict["cat_score"] = float(v.cat_score)
        history.append(v_dict)

    if not history:
        # Fallback initial visit if none recorded
        history = [{
            "patient_id": patient_rec.patient_id,
            "visit_number": 1,
            "months_since_baseline": 0.0,
            "age_at_visit": float(patient_rec.age_at_baseline),
            "smoking_status_at_visit": patient_rec.smoking_status_baseline,
            "activity_level_at_visit": "moderate",
            "fev1_liters": float(patient_rec.baseline_fev1_liters),
            "fvc_liters": float(patient_rec.baseline_fvc_liters),
            "fev1_fvc_ratio": float(patient_rec.baseline_fev1_fvc_ratio),
            "exacerbations_this_visit": 0,
            "measurement_source": "clinic",
        }]

    return TwinState.from_dict({
        "patient_id": patient_rec.patient_id,
        "static": static_data,
        "history": history,
        "current": history[-1],
    })


def twin_state_to_db(twin: TwinState, db: Session) -> PatientRecord:
    """Save or update a TwinState instance and its visits into the SQLite database."""
    patient_rec = db.query(PatientRecord).filter_by(patient_id=twin.patient_id).first()

    static = twin.static
    if not patient_rec:
        patient_rec = PatientRecord(
            patient_id=twin.patient_id,
            sex=str(static.get("sex", "M")),
            age_at_baseline=float(static.get("age_at_baseline", 65.0)),
            gold_stage_baseline=str(static.get("gold_stage_baseline", "II (Moderate)")),
            smoking_status_baseline=str(static.get("smoking_status_baseline", "former")),
            pack_years=float(static.get("pack_years", 30.0)),
            baseline_fev1_liters=float(static.get("baseline_fev1_liters", 1.85)),
            baseline_fvc_liters=float(static.get("baseline_fvc_liters", 3.10)),
            baseline_fev1_fvc_ratio=float(static.get("baseline_fev1_fvc_ratio", 0.60)),
            bmi=float(static.get("bmi", 26.0)),
        )
        db.add(patient_rec)
        db.flush()

    # Track existing visit numbers
    existing_visits = {v.visit_number: v for v in patient_rec.visits}

    for v_dict in twin.history:
        v_num = int(v_dict.get("visit_number", 1))
        if v_num in existing_visits:
            v_rec = existing_visits[v_num]
            v_rec.months_since_baseline = float(v_dict.get("months_since_baseline", 0.0))
            v_rec.age_at_visit = float(v_dict.get("age_at_visit", 65.0))
            v_rec.smoking_status_at_visit = str(v_dict.get("smoking_status_at_visit", "former"))
            v_rec.activity_level_at_visit = str(v_dict.get("activity_level_at_visit", "moderate"))
            v_rec.fev1_liters = float(v_dict.get("fev1_liters", 1.85))
            v_rec.fvc_liters = float(v_dict.get("fvc_liters", 3.10))
            v_rec.fev1_fvc_ratio = float(v_dict.get("fev1_fvc_ratio", 0.60))
            v_rec.exacerbations_this_visit = int(v_dict.get("exacerbations_this_visit", 0))
            v_rec.measurement_source = str(v_dict.get("measurement_source", "clinic"))
            v_rec.spo2_pct = float(v_dict["spo2_pct"]) if "spo2_pct" in v_dict and pd.notna(v_dict["spo2_pct"]) else None
            v_rec.cat_score = float(v_dict["cat_score"]) if "cat_score" in v_dict and pd.notna(v_dict["cat_score"]) else None
        else:
            new_v = VisitRecord(
                patient_id=twin.patient_id,
                visit_number=v_num,
                months_since_baseline=float(v_dict.get("months_since_baseline", 0.0)),
                age_at_visit=float(v_dict.get("age_at_visit", 65.0)),
                smoking_status_at_visit=str(v_dict.get("smoking_status_at_visit", "former")),
                activity_level_at_visit=str(v_dict.get("activity_level_at_visit", "moderate")),
                fev1_liters=float(v_dict.get("fev1_liters", 1.85)),
                fvc_liters=float(v_dict.get("fvc_liters", 3.10)),
                fev1_fvc_ratio=float(v_dict.get("fev1_fvc_ratio", 0.60)),
                exacerbations_this_visit=int(v_dict.get("exacerbations_this_visit", 0)),
                measurement_source=str(v_dict.get("measurement_source", "clinic")),
                spo2_pct=float(v_dict["spo2_pct"]) if "spo2_pct" in v_dict and pd.notna(v_dict["spo2_pct"]) else None,
                cat_score=float(v_dict["cat_score"]) if "cat_score" in v_dict and pd.notna(v_dict["cat_score"]) else None,
            )
            db.add(new_v)

    db.commit()
    db.refresh(patient_rec)
    return patient_rec


def seed_database_if_empty(
    db: Session,
    csv_path: Optional[Union[str, Path]] = None,
    limit: Optional[int] = None,
) -> int:
    """Populate SQLite database from synthetic CSV cohort if empty.

    Returns the count of seeded patients.
    """
    existing_count = db.query(PatientRecord).count()
    if existing_count > 0:
        logger.info("SQLite database already populated with %d patients.", existing_count)
        return 0

    path = Path(csv_path) if csv_path else Path("data/raw/copd_synthetic_longitudinal.csv")
    if not path.exists():
        logger.warning("CSV path '%s' not found for seeding database.", path)
        return 0

    df = pd.read_csv(path)
    if df.empty:
        return 0

    grouped = df.groupby("patient_id", sort=False)
    seeded_count = 0

    for pid, p_df in grouped:
        twin = TwinState.from_dataframe(p_df)
        twin_state_to_db(twin, db)
        seeded_count += 1
        if limit is not None and seeded_count >= limit:
            break

    logger.info("Successfully seeded SQLite database with %d synthetic patients from %s.", seeded_count, path)
    return seeded_count


def reset_database(
    db: Session,
    csv_path: Optional[Union[str, Path]] = None,
    limit: Optional[int] = None,
) -> None:
    """Clear all records and re-seed the SQLite database."""
    db.query(VisitRecord).delete()
    db.query(PatientRecord).delete()
    db.commit()
    seed_database_if_empty(db, csv_path=csv_path, limit=limit)

