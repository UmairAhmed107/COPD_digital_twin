"""Model evaluation and comparison module for COPD Digital Twin.

Provides functions to:
- Load trained models (Random Forest, XGBoost) and preprocessors from artifacts.
- Compute or extract regression performance metrics (MAE, RMSE, R²).
- Extract feature importances for both Random Forest and XGBoost.
- Structure comparison outputs to directly populate the `ModelComparisonResponse` schema
  for FastAPI endpoints and Next.js frontend consumption.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd

try:
    from src.data_prep import APPROVED_FEATURES, get_features_and_target
    from src.model import DEFAULT_ARTIFACTS_DIR, evaluate_predictions
except ImportError:
    from data_prep import APPROVED_FEATURES, get_features_and_target
    from model import DEFAULT_ARTIFACTS_DIR, evaluate_predictions

try:
    from api.schemas import ModelComparisonResponse
except ImportError:
    try:
        from schemas import ModelComparisonResponse
    except ImportError:
        ModelComparisonResponse = None


def load_evaluation_artifacts(
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
) -> Dict[str, Any]:
    """Load preprocessor, models, and metadata from the artifacts directory.

    Parameters
    ----------
    artifacts_dir : Union[str, Path], default='artifacts'
        Path to directory containing saved joblib artifacts.

    Returns
    -------
    Dict[str, Any]
        Dictionary with keys 'preprocessor', 'rf_model', 'xgb_model', and optional 'metadata'.

    Raises
    ------
    FileNotFoundError
        If core model artifacts (preprocessor, rf_model, xgb_model) are missing.
    """
    target_dir = Path(artifacts_dir).resolve()
    if not target_dir.exists():
        raise FileNotFoundError(f"Artifacts directory does not exist: {target_dir}")

    preprocessor_path = target_dir / "preprocessor.joblib"
    rf_path = target_dir / "rf_model.joblib"
    xgb_path = target_dir / "xgb_model.joblib"
    metadata_path = target_dir / "model_metadata.joblib"

    missing = []
    if not preprocessor_path.exists():
        missing.append("preprocessor.joblib")
    if not rf_path.exists():
        missing.append("rf_model.joblib")
    if not xgb_path.exists():
        missing.append("xgb_model.joblib")

    if missing:
        raise FileNotFoundError(
            f"Missing required artifact(s) in {target_dir}: {', '.join(missing)}"
        )

    preprocessor = joblib.load(preprocessor_path)
    rf_model = joblib.load(rf_path)
    xgb_model = joblib.load(xgb_path)
    metadata = joblib.load(metadata_path) if metadata_path.exists() else None

    return {
        "preprocessor": preprocessor,
        "rf_model": rf_model,
        "xgb_model": xgb_model,
        "metadata": metadata,
    }


def extract_feature_importances(
    model: Any,
    preprocessor: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    round_digits: int = 4,
) -> Dict[str, float]:
    """Extract feature importances from a trained regressor.

    Parameters
    ----------
    model : Any
        Trained model exposing `feature_importances_` attribute.
    preprocessor : Optional[Any], default=None
        Fitted ColumnTransformer or encoder providing feature names via `get_feature_names_out()`.
    feature_names : Optional[List[str]], default=None
        Explicit list of feature names matching model input dimensionality.
    round_digits : int, default=4
        Decimal places for rounding importance values.

    Returns
    -------
    Dict[str, float]
        Dictionary mapping feature name to importance score, sorted descending by importance.
    """
    if not hasattr(model, "feature_importances_"):
        raise AttributeError(f"Model {type(model)} does not have feature_importances_ attribute.")

    importances = model.feature_importances_

    # Determine feature names
    names: List[str]
    if feature_names is not None:
        names = list(feature_names)
    elif preprocessor is not None and hasattr(preprocessor, "get_feature_names_out"):
        names = list(preprocessor.get_feature_names_out())
    else:
        names = [f"feature_{i}" for i in range(len(importances))]

    if len(names) != len(importances):
        raise ValueError(
            f"Mismatch between number of feature names ({len(names)}) and importances ({len(importances)})."
        )

    importance_dict = {
        feat: round(float(imp), round_digits)
        for feat, imp in zip(names, importances)
    }

    # Sort descending by importance
    return dict(sorted(importance_dict.items(), key=lambda item: item[1], reverse=True))


def compute_model_metrics(
    model: Any,
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    preprocessor: Optional[Any] = None,
) -> Dict[str, float]:
    """Compute regression performance metrics (MAE, RMSE, R²) on a dataset.

    Parameters
    ----------
    model : Any
        Trained regression model with `.predict()`.
    X : Union[pd.DataFrame, np.ndarray]
        Input features (either raw approved features or preprocessed array).
    y : Union[pd.Series, np.ndarray]
        Ground truth target values.
    preprocessor : Optional[Any], default=None
        Preprocessor to transform X if raw features are provided.

    Returns
    -------
    Dict[str, float]
        Dictionary containing 'mae', 'rmse', and 'r2' as python floats.
    """
    if preprocessor is not None and isinstance(X, pd.DataFrame):
        # Isolate approved features if present in DataFrame columns
        matching_approved = [c for c in APPROVED_FEATURES if c in X.columns]
        if len(matching_approved) == len(APPROVED_FEATURES):
            X_input = X[APPROVED_FEATURES].copy()
        else:
            X_input = X.copy()
        X_trans = preprocessor.transform(X_input)
    else:
        X_trans = X

    preds = model.predict(X_trans)
    return evaluate_predictions(y, preds)


def get_model_comparison(
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    test_df: Optional[pd.DataFrame] = None,
    feature_importance_model: str = "rf",
) -> Dict[str, Any]:
    """Generate model comparison metrics and feature importances for RF and XGBoost.

    Can retrieve pre-computed evaluation metrics directly from saved `model_metadata.joblib`,
    or dynamically compute fresh metrics if a `test_df` is provided.

    Parameters
    ----------
    artifacts_dir : Union[str, Path], default='artifacts'
        Directory containing .joblib artifact files.
    test_df : Optional[pd.DataFrame], default=None
        Optional test dataset for dynamic evaluation. If None, loaded metadata is used.
    feature_importance_model : str, default='rf'
        Which model's feature importances to use for the top-level `feature_importances`
        field: 'rf' / 'random_forest' or 'xgb' / 'xgboost'.

    Returns
    -------
    Dict[str, Any]
        Dictionary structured to populate `ModelComparisonResponse`:
        {
            "rf_metrics": {"mae": float, "rmse": float, "r2": float},
            "xgb_metrics": {"mae": float, "rmse": float, "r2": float},
            "feature_importances": Dict[str, float],
            "rf_feature_importances": Dict[str, float],
            "xgb_feature_importances": Dict[str, float],
        }
    """
    artifacts = load_evaluation_artifacts(artifacts_dir)
    preprocessor = artifacts["preprocessor"]
    rf_model = artifacts["rf_model"]
    xgb_model = artifacts["xgb_model"]
    metadata = artifacts["metadata"]

    # Compute or retrieve metrics
    if test_df is not None:
        X_test, y_test = get_features_and_target(test_df)
        rf_metrics = compute_model_metrics(rf_model, X_test, y_test, preprocessor=preprocessor)
        xgb_metrics = compute_model_metrics(xgb_model, X_test, y_test, preprocessor=preprocessor)
        rf_importances = extract_feature_importances(rf_model, preprocessor=preprocessor)
        xgb_importances = extract_feature_importances(xgb_model, preprocessor=preprocessor)
    elif metadata is not None and "rf_metrics" in metadata and "xgb_metrics" in metadata:
        rf_metrics = metadata["rf_metrics"]
        xgb_metrics = metadata["xgb_metrics"]
        rf_raw = metadata.get("rf_feature_importances") or extract_feature_importances(
            rf_model, preprocessor=preprocessor
        )
        xgb_raw = metadata.get("xgb_feature_importances") or extract_feature_importances(
            xgb_model, preprocessor=preprocessor
        )
        rf_importances = dict(sorted(rf_raw.items(), key=lambda item: item[1], reverse=True))
        xgb_importances = dict(sorted(xgb_raw.items(), key=lambda item: item[1], reverse=True))
    else:
        # Fall back to extracting feature importances directly from models, but metrics require test data
        raise ValueError(
            "Evaluation metrics could not be determined: no test_df was provided and "
            "model_metadata.joblib is either missing or does not contain pre-computed metrics."
        )

    # Choose primary feature_importances dictionary
    norm_fi_model = feature_importance_model.lower().strip()
    if norm_fi_model in ("xgb", "xgboost"):
        primary_fi = xgb_importances
    else:
        primary_fi = rf_importances

    return {
        "rf_metrics": rf_metrics,
        "xgb_metrics": xgb_metrics,
        "feature_importances": primary_fi,
        "rf_feature_importances": rf_importances,
        "xgb_feature_importances": xgb_importances,
    }


def get_model_comparison_response(
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    test_df: Optional[pd.DataFrame] = None,
    feature_importance_model: str = "rf",
) -> Any:
    """Generate model comparison structured as a `ModelComparisonResponse` Pydantic instance.

    Parameters
    ----------
    artifacts_dir : Union[str, Path], default='artifacts'
        Artifacts directory.
    test_df : Optional[pd.DataFrame], default=None
        Optional test dataset.
    feature_importance_model : str, default='rf'
        'rf' or 'xgb'.

    Returns
    -------
    ModelComparisonResponse
        Validated Pydantic model instance.
    """
    comparison = get_model_comparison(
        artifacts_dir=artifacts_dir,
        test_df=test_df,
        feature_importance_model=feature_importance_model,
    )
    if ModelComparisonResponse is None:
        return comparison
    return ModelComparisonResponse(**comparison)


def format_comparison_table(comparison: Dict[str, Any]) -> str:
    """Format model comparison results into a readable text table.

    Parameters
    ----------
    comparison : Dict[str, Any]
        Dictionary returned by `get_model_comparison`.

    Returns
    -------
    str
        Formatted comparison table.
    """
    rf = comparison["rf_metrics"]
    xgb = comparison["xgb_metrics"]

    def pick_winner(metric_name: str) -> str:
        rf_val = rf[metric_name]
        xgb_val = xgb[metric_name]
        if metric_name == "r2":
            if rf_val > xgb_val:
                return "Random Forest"
            elif xgb_val > rf_val:
                return "XGBoost"
            return "Tie"
        else:
            if rf_val < xgb_val:
                return "Random Forest"
            elif xgb_val < rf_val:
                return "XGBoost"
            return "Tie"

    lines = [
        "| Metric | Random Forest | XGBoost | Outperforming |",
        "| :--- | :---: | :---: | :---: |",
        f"| MAE  | {rf['mae']:.4f} | {xgb['mae']:.4f} | {pick_winner('mae')} |",
        f"| RMSE | {rf['rmse']:.4f} | {xgb['rmse']:.4f} | {pick_winner('rmse')} |",
        f"| R²   | {rf['r2']:.4f} | {xgb['r2']:.4f} | {pick_winner('r2')} |",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    try:
        data = get_model_comparison(DEFAULT_ARTIFACTS_DIR)
        print("\n=== Model Comparison: Random Forest vs. XGBoost ===")
        print(format_comparison_table(data))

        print("\n--- Top 5 Feature Importances (Random Forest) ---")
        for k, v in list(data["rf_feature_importances"].items())[:5]:
            print(f"  {k}: {v:.4f}")

        print("\n--- Top 5 Feature Importances (XGBoost) ---")
        for k, v in list(data["xgb_feature_importances"].items())[:5]:
            print(f"  {k}: {v:.4f}")

        response = get_model_comparison_response(DEFAULT_ARTIFACTS_DIR)
        print("\nModelComparisonResponse schema validation: SUCCESS")
    except Exception as exc:
        print(f"Error evaluating models: {exc}", file=sys.stderr)
        sys.exit(1)
