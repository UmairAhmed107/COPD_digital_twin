"""Unit tests for COPD Digital Twin model training, evaluation, and inference.

Verifies:
- Zero longitudinal patient leakage via group splitting (GroupShuffleSplit).
- Successful training of Random Forest and XGBoost regressors.
- Correct artifact persistence (.joblib files).
- Inference function `predict_fev1` for both single and batch inputs.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBRegressor

from src.data_prep import APPROVED_FEATURES
from src.model import (
    evaluate_predictions,
    load_exac_classifier,
    load_model_artifacts,
    predict_dual,
    predict_exacerbation_risk,
    predict_fev1,
    split_data_by_patient_group,
    train_models,
)


def test_group_split_zero_leakage(mock_dataset):
    """Verify GroupShuffleSplit prevents any patient overlap between train and test."""
    train_df, test_df = split_data_by_patient_group(
        mock_dataset,
        test_size=0.5,
        random_state=42,
    )

    assert len(train_df) > 0
    assert len(test_df) > 0

    train_pids = set(train_df["patient_id"])
    test_pids = set(test_df["patient_id"])

    # Strict zero longitudinal leakage constraint
    assert train_pids.isdisjoint(
        test_pids
    ), f"Leakage detected! Patients in both train and test: {train_pids & test_pids}"

    # Verify that all visits for patient P0001 (which has 2 visits) stay together
    if "P0001" in train_pids:
        assert (train_df["patient_id"] == "P0001").sum() == 2
        assert (test_df["patient_id"] == "P0001").sum() == 0
    else:
        assert (test_df["patient_id"] == "P0001").sum() == 2
        assert (train_df["patient_id"] == "P0001").sum() == 0


def test_group_split_input_validation():
    """Verify error handling on malformed or single-patient datasets."""
    df_no_pid = pd.DataFrame({"age": [65, 70]})
    with pytest.raises(KeyError, match="patient_id"):
        split_data_by_patient_group(df_no_pid)

    df_one_patient = pd.DataFrame({"patient_id": ["P0001", "P0001"], "val": [1, 2]})
    with pytest.raises(ValueError, match="At least 2 unique patients"):
        split_data_by_patient_group(df_one_patient)


def test_evaluate_predictions():
    """Verify regression metrics calculation (MAE, RMSE, R2)."""
    y_true = np.array([1.5, 2.0, 2.5])
    y_pred = np.array([1.5, 2.0, 2.5])
    metrics = evaluate_predictions(y_true, y_pred)

    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["r2"] == 1.0

    y_imperfect = np.array([1.4, 2.1, 2.4])
    metrics_imp = evaluate_predictions(y_true, y_imperfect)
    assert metrics_imp["mae"] > 0.0
    assert metrics_imp["rmse"] > 0.0
    assert metrics_imp["r2"] < 1.0


def test_train_models_pipeline_and_artifacts(mock_dataset, tmp_path):
    """Verify train_models trains RF regressor, XGBoost, and RF classifier and saves .joblib artifacts."""
    results = train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    # Check returned model instances
    assert isinstance(results["rf_model"], RandomForestRegressor)
    assert isinstance(results["xgb_model"], XGBRegressor)
    assert isinstance(results["exac_model"], RandomForestClassifier)
    assert isinstance(results["preprocessor"], ColumnTransformer)

    # Check metrics structure
    metrics = results["metrics"]
    for model_key in ["rf_metrics", "xgb_metrics"]:
        assert model_key in metrics
        for metric_name in ["mae", "rmse", "r2"]:
            assert metric_name in metrics[model_key]
            assert isinstance(metrics[model_key][metric_name], float)

    # Check exacerbation metrics
    assert "exac_metrics" in metrics

    # Check feature importances
    for imp_key in ["rf_feature_importances", "xgb_feature_importances"]:
        assert imp_key in metrics
        assert isinstance(metrics[imp_key], dict)
        assert len(metrics[imp_key]) > 0

    # Verify artifacts exist on disk
    expected_artifacts = [
        tmp_path / "preprocessor.joblib",
        tmp_path / "rf_model.joblib",
        tmp_path / "xgb_model.joblib",
        tmp_path / "exac_classifier.joblib",
        tmp_path / "model_metadata.joblib",
    ]
    for art in expected_artifacts:
        assert art.exists(), f"Expected artifact {art.name} was not saved!"


def test_predict_fev1_inference(mock_dataset, tmp_path):
    """Verify predict_fev1 supports single-dict and batch DataFrame inputs for RF and XGBoost."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    sample_row = mock_dataset.iloc[0][APPROVED_FEATURES].to_dict()

    # 1. Test single dict input -> returns float
    pred_rf_single = predict_fev1(sample_row, model_type="random_forest", artifacts_dir=tmp_path)
    assert isinstance(pred_rf_single, float)
    assert 0.2 <= pred_rf_single <= 5.0

    pred_xgb_single = predict_fev1(sample_row, model_type="xgboost", artifacts_dir=tmp_path)
    assert isinstance(pred_xgb_single, float)
    assert 0.2 <= pred_xgb_single <= 5.0

    # 2. Test aliases ("rf", "xgb")
    pred_rf_alias = predict_fev1(sample_row, model_type="rf", artifacts_dir=tmp_path)
    assert pred_rf_alias == pytest.approx(pred_rf_single, rel=1e-5)

    pred_xgb_alias = predict_fev1(sample_row, model_type="xgb", artifacts_dir=tmp_path)
    assert pred_xgb_alias == pytest.approx(pred_xgb_single, rel=1e-5)

    # 3. Test batch DataFrame input -> returns 1D numpy array
    batch_df = mock_dataset[APPROVED_FEATURES].copy()
    pred_rf_batch = predict_fev1(batch_df, model_type="random_forest", artifacts_dir=tmp_path)
    assert isinstance(pred_rf_batch, np.ndarray)
    assert len(pred_rf_batch) == len(mock_dataset)

    pred_xgb_batch = predict_fev1(batch_df, model_type="xgboost", artifacts_dir=tmp_path)
    assert isinstance(pred_xgb_batch, np.ndarray)
    assert len(pred_xgb_batch) == len(mock_dataset)


def test_predict_fev1_unseen_categories(mock_dataset, tmp_path):
    """Verify inference gracefully handles unseen category values without crashing."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    unseen_row = mock_dataset.iloc[0][APPROVED_FEATURES].to_dict()
    unseen_row["smoking_status_at_visit"] = "novel_unseen_status"
    unseen_row["gold_stage_baseline"] = "Stage_Unknown"

    pred = predict_fev1(unseen_row, model_type="random_forest", artifacts_dir=tmp_path)
    assert isinstance(pred, float)
    assert not np.isnan(pred)


def test_predict_fev1_missing_features(mock_dataset, tmp_path):
    """Verify predict_fev1 raises KeyError when approved feature columns are missing."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    incomplete_row = {"age_at_visit": 65.0, "sex": "M"}
    with pytest.raises(KeyError, match="Input features missing"):
        predict_fev1(incomplete_row, artifacts_dir=tmp_path)


def test_predict_fev1_invalid_model_type(mock_dataset, tmp_path):
    """Verify predict_fev1 raises ValueError on unsupported model_type."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    sample_row = mock_dataset.iloc[0][APPROVED_FEATURES].to_dict()
    with pytest.raises(ValueError, match="Unsupported model_type"):
        predict_fev1(sample_row, model_type="support_vector_machine", artifacts_dir=tmp_path)


def test_predict_exacerbation_risk(mock_dataset, tmp_path):
    """Verify predict_exacerbation_risk returns calibrated probability percentage."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    sample_row = mock_dataset.iloc[0][APPROVED_FEATURES].to_dict()

    # Single dict input
    risk_single = predict_exacerbation_risk(sample_row, artifacts_dir=tmp_path, as_pct=True)
    assert isinstance(risk_single, float)
    assert 0.0 <= risk_single <= 100.0

    # Batch DataFrame input
    batch_df = mock_dataset[APPROVED_FEATURES].copy()
    risk_batch = predict_exacerbation_risk(batch_df, artifacts_dir=tmp_path, as_pct=True)
    assert isinstance(risk_batch, np.ndarray)
    assert len(risk_batch) == len(mock_dataset)
    assert all(0.0 <= r <= 100.0 for r in risk_batch)


def test_predict_dual(mock_dataset, tmp_path):
    """Verify predict_dual returns both FEV1 decline and exacerbation risk with display string."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    sample_row = mock_dataset.iloc[0][APPROVED_FEATURES].to_dict()
    res = predict_dual(sample_row, model_type="random_forest", artifacts_dir=tmp_path)

    assert isinstance(res, dict)
    assert "predicted_fev1_liters" in res
    assert "exacerbation_risk_prob" in res
    assert "exacerbation_risk_pct" in res
    assert "risk_display" in res
    assert "% risk" in res["risk_display"]
    assert 0.2 <= res["predicted_fev1_liters"] <= 5.0
    assert 0.0 <= res["exacerbation_risk_pct"] <= 100.0


def test_predict_fev1_with_return_risk(mock_dataset, tmp_path):
    """Verify predict_fev1 returns tuple (fev1, risk_pct) when return_risk=True."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    sample_row = mock_dataset.iloc[0][APPROVED_FEATURES].to_dict()
    fev1, risk_pct = predict_fev1(sample_row, artifacts_dir=tmp_path, return_risk=True)

    assert isinstance(fev1, float)
    assert isinstance(risk_pct, float)
    assert 0.2 <= fev1 <= 5.0
    assert 0.0 <= risk_pct <= 100.0
