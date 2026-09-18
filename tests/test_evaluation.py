"""Unit tests for COPD Digital Twin model evaluation and comparison module.

Verifies:
- Loading of preprocessor, Random Forest, XGBoost, and metadata artifacts.
- Extraction of feature importances sorted descending.
- Computation of regression metrics (MAE, RMSE, R²).
- Dynamic evaluation with test DataFrames vs. metadata-based fast path.
- Exact compliance with the ModelComparisonResponse Pydantic schema in api/schemas.py.
- Formatting of comparison tables.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from api.schemas import ModelComparisonResponse
from src.data_prep import APPROVED_FEATURES
from src.evaluation import (
    compute_model_metrics,
    extract_feature_importances,
    format_comparison_table,
    get_model_comparison,
    get_model_comparison_response,
    load_evaluation_artifacts,
)
from src.model import DEFAULT_ARTIFACTS_DIR, train_models


def test_load_evaluation_artifacts_default():
    """Verify loading artifacts from the default artifacts/ directory."""
    if not (DEFAULT_ARTIFACTS_DIR / "rf_model.joblib").exists():
        pytest.skip("Default artifacts not present on disk.")

    artifacts = load_evaluation_artifacts(DEFAULT_ARTIFACTS_DIR)

    assert "preprocessor" in artifacts
    assert "rf_model" in artifacts
    assert "xgb_model" in artifacts
    assert "metadata" in artifacts

    assert isinstance(artifacts["preprocessor"], ColumnTransformer)
    assert isinstance(artifacts["rf_model"], RandomForestRegressor)
    assert isinstance(artifacts["xgb_model"], XGBRegressor)
    assert isinstance(artifacts["metadata"], dict)


def test_load_evaluation_artifacts_missing_dir(tmp_path):
    """Verify FileNotFoundError is raised if the directory does not exist."""
    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError, match="Artifacts directory does not exist"):
        load_evaluation_artifacts(non_existent)


def test_load_evaluation_artifacts_missing_files(tmp_path):
    """Verify FileNotFoundError is raised if any core artifact is missing."""
    empty_dir = tmp_path / "empty_artifacts"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Missing required artifact"):
        load_evaluation_artifacts(empty_dir)


def test_extract_feature_importances():
    """Verify feature importances are extracted, named, sorted descending, and rounded."""
    class DummyModel:
        feature_importances_ = np.array([0.1, 0.7, 0.2])

    dummy_model = DummyModel()
    names = ["feat_a", "feat_b", "feat_c"]

    importances = extract_feature_importances(dummy_model, feature_names=names, round_digits=2)

    assert list(importances.keys()) == ["feat_b", "feat_c", "feat_a"]
    assert importances["feat_b"] == 0.7
    assert importances["feat_c"] == 0.2
    assert importances["feat_a"] == 0.1

    # Verify fallback name generation when no names or preprocessor provided
    importances_fallback = extract_feature_importances(dummy_model)
    assert list(importances_fallback.keys()) == ["feature_1", "feature_2", "feature_0"]

    # Verify error on model without feature_importances_
    class NoFIModel:
        pass

    with pytest.raises(AttributeError, match="does not have feature_importances_"):
        extract_feature_importances(NoFIModel())

    # Verify error on mismatched name count
    with pytest.raises(ValueError, match="Mismatch between number of feature names"):
        extract_feature_importances(dummy_model, feature_names=["only_one"])


def test_compute_model_metrics(mock_dataset, tmp_path):
    """Verify compute_model_metrics calculates MAE, RMSE, and R2."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )
    artifacts = load_evaluation_artifacts(tmp_path)
    rf_model = artifacts["rf_model"]
    preprocessor = artifacts["preprocessor"]

    X = mock_dataset[APPROVED_FEATURES]
    y = mock_dataset["fev1_liters"]

    metrics = compute_model_metrics(rf_model, X, y, preprocessor=preprocessor)

    for metric_name in ["mae", "rmse", "r2"]:
        assert metric_name in metrics
        assert isinstance(metrics[metric_name], float)
        assert not np.isnan(metrics[metric_name])


def test_get_model_comparison_from_metadata(mock_dataset, tmp_path):
    """Verify retrieving comparison directly from metadata joblib."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    # Test default feature_importance_model ('rf')
    comparison_rf = get_model_comparison(tmp_path, test_df=None, feature_importance_model="rf")
    assert "rf_metrics" in comparison_rf
    assert "xgb_metrics" in comparison_rf
    assert "feature_importances" in comparison_rf
    assert "rf_feature_importances" in comparison_rf
    assert "xgb_feature_importances" in comparison_rf

    # Feature importances must be sorted descending
    rf_fi_values = list(comparison_rf["feature_importances"].values())
    assert rf_fi_values == sorted(rf_fi_values, reverse=True)

    # Test 'xgb' selection for feature_importances
    comparison_xgb = get_model_comparison(tmp_path, test_df=None, feature_importance_model="xgb")
    assert comparison_xgb["feature_importances"] == comparison_xgb["xgb_feature_importances"]


def test_get_model_comparison_with_test_df(mock_dataset, tmp_path):
    """Verify dynamic evaluation against a passed test DataFrame."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    comparison = get_model_comparison(tmp_path, test_df=mock_dataset, feature_importance_model="rf")

    assert "rf_metrics" in comparison
    assert "xgb_metrics" in comparison
    assert comparison["rf_metrics"]["mae"] >= 0.0
    assert comparison["xgb_metrics"]["mae"] >= 0.0


def test_model_comparison_response_schema_validation(mock_dataset, tmp_path):
    """Verify get_model_comparison_response produces a valid ModelComparisonResponse Pydantic instance."""
    train_models(
        mock_dataset,
        artifacts_dir=tmp_path,
        test_size=0.5,
        random_state=42,
        save_artifacts=True,
    )

    response = get_model_comparison_response(tmp_path)

    assert isinstance(response, ModelComparisonResponse)
    assert hasattr(response, "rf_metrics")
    assert hasattr(response, "xgb_metrics")
    assert hasattr(response, "feature_importances")

    # Verify Pydantic dump
    dumped = response.model_dump()
    assert isinstance(dumped["rf_metrics"], dict)
    assert isinstance(dumped["xgb_metrics"], dict)
    assert isinstance(dumped["feature_importances"], dict)
    for m in ["mae", "rmse", "r2"]:
        assert m in dumped["rf_metrics"]
        assert m in dumped["xgb_metrics"]


def test_format_comparison_table():
    """Verify markdown comparison table output."""
    comparison = {
        "rf_metrics": {"mae": 0.0543, "rmse": 0.0681, "r2": 0.9931},
        "xgb_metrics": {"mae": 0.0530, "rmse": 0.0667, "r2": 0.9934},
        "feature_importances": {},
    }
    table = format_comparison_table(comparison)

    assert "| Metric | Random Forest | XGBoost | Outperforming |" in table
    assert "MAE" in table
    assert "RMSE" in table
    assert "0.0543" in table
    assert "0.0530" in table
    assert "XGBoost" in table


def test_get_model_comparison_missing_metadata_and_test_df(tmp_path):
    """Verify ValueError when both metadata and test_df are absent."""
    import joblib
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from xgboost import XGBRegressor

    # Save dummy models without metadata
    joblib.dump(ColumnTransformer([]), tmp_path / "preprocessor.joblib")
    joblib.dump(RandomForestRegressor(), tmp_path / "rf_model.joblib")
    joblib.dump(XGBRegressor(), tmp_path / "xgb_model.joblib")

    with pytest.raises(ValueError, match="Evaluation metrics could not be determined"):
        get_model_comparison(tmp_path, test_df=None)
