"""Machine learning training and inference pipeline for COPD Digital Twin.

Trains Random Forest and XGBoost regressors to predict lung function (`fev1_liters`)
using the 9 approved input features. Enforces zero longitudinal leakage across train
and test sets via patient-level group splitting (GroupShuffleSplit).
Persists fitted preprocessors and models as .joblib artifacts for downstream API/simulator use.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor

try:
    from src.data_prep import (
        APPROVED_FEATURES,
        EXAC_TARGET_COL,
        TARGET_COL,
        build_preprocessor,
        clean_data,
        get_features_and_target,
        load_data,
    )
except ImportError:
    from data_prep import (
        APPROVED_FEATURES,
        EXAC_TARGET_COL,
        TARGET_COL,
        build_preprocessor,
        clean_data,
        get_features_and_target,
        load_data,
    )

DEFAULT_ARTIFACTS_DIR = Path("artifacts")

# Global in-memory cache for loaded model artifacts: (artifacts_dir, model_type) -> (preprocessor, model)
_MODEL_CACHE: Dict[Tuple[str, str], Any] = {}
_PREPROCESSOR_CACHE: Dict[str, Any] = {}


def split_data_by_patient_group(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset into train and test sets grouped by patient_id using GroupShuffleSplit.

    Ensures that all longitudinal visits of any patient belong strictly to either
    the train set or the test set, preventing feature and trajectory leakage.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing `patient_id`.
    test_size : float, default=0.2
        Fraction of patient groups to allocate to the test split.
    random_state : int, default=42
        Random seed for reproducible splitting.

    Returns
    -------
    train_df : pd.DataFrame
        Records for training patients.
    test_df : pd.DataFrame
        Records for test patients.
    """
    if "patient_id" not in df.columns:
        raise KeyError("Dataframe must contain 'patient_id' column for group splitting.")

    unique_patients = df["patient_id"].unique()
    if len(unique_patients) < 2:
        raise ValueError("At least 2 unique patients are required for patient-level group split.")

    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_idx, test_idx = next(gss.split(df, groups=df["patient_id"]))

    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)

    # Sanity check: zero overlapping patients
    overlap = set(train_df["patient_id"]).intersection(set(test_df["patient_id"]))
    if overlap:
        raise RuntimeError(f"Longitudinal leakage detected! Overlapping patient IDs: {overlap}")

    return train_df, test_df


def evaluate_predictions(y_true: Union[pd.Series, np.ndarray], y_pred: np.ndarray) -> Dict[str, float]:
    """Compute regression metrics: MAE, RMSE, and R2.

    Parameters
    ----------
    y_true : Union[pd.Series, np.ndarray]
        Ground truth target values.
    y_pred : np.ndarray
        Model predictions.

    Returns
    -------
    Dict[str, float]
        Dictionary with 'mae', 'rmse', and 'r2' rounded to 4 decimals.
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    if len(y_true) >= 2:
        r2 = float(r2_score(y_true, y_pred))
    else:
        r2 = 0.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
    }


def train_models(
    df: pd.DataFrame,
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    test_size: float = 0.2,
    random_state: int = 42,
    save_artifacts: bool = True,
    clean_input: bool = True,
) -> Dict[str, Any]:
    """Train Random Forest and XGBoost models to predict `fev1_liters`.

    Executes:
    1. Optional data cleaning and synthetic outlier removal.
    2. Zero-leakage patient-level group splitting.
    3. Feature/target extraction guarding against downstream leakage.
    4. Categorical encoding via scikit-learn ColumnTransformer.
    5. Training of both RandomForestRegressor and XGBRegressor.
    6. Performance evaluation on held-out patient test set (MAE, RMSE, R2).
    7. Persistence of trained models and metadata to .joblib files.

    Parameters
    ----------
    df : pd.DataFrame
        Longitudinal patient dataset.
    artifacts_dir : Union[str, Path], default='artifacts'
        Target directory for saved model artifacts.
    test_size : float, default=0.2
        Proportion of patients for test set.
    random_state : int, default=42
        Seed for reproducibility.
    save_artifacts : bool, default=True
        Whether to save models and preprocessor to disk.
    clean_input : bool, default=True
        Whether to clean dataset (remove outlier_fev1) before splitting.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing trained models, preprocessor, and evaluation metrics.
    """
    working_df = clean_data(df, drop_outliers=True) if clean_input else df.copy()

    # 1. Group split by patient_id
    train_df, test_df = split_data_by_patient_group(
        working_df,
        test_size=test_size,
        random_state=random_state,
    )

    # 2. Extract features and targets (strictly checks for leakage)
    X_train, y_train, y_train_exac = get_features_and_target(train_df, return_exac=True)
    X_test, y_test, y_test_exac = get_features_and_target(test_df, return_exac=True)

    # 3. Fit preprocessor on training data only
    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    # 4. Train Random Forest Regressor (FEV1 decline)
    rf_model = RandomForestRegressor(
        n_estimators=100,
        random_state=random_state,
        n_jobs=-1,
    )
    rf_model.fit(X_train_proc, y_train)
    rf_preds = rf_model.predict(X_test_proc)
    rf_metrics = evaluate_predictions(y_test, rf_preds)

    # 5. Train XGBoost Regressor (FEV1 decline)
    xgb_model = XGBRegressor(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        random_state=random_state,
        n_jobs=-1,
    )
    xgb_model.fit(X_train_proc, y_train)
    xgb_preds = xgb_model.predict(X_test_proc)
    xgb_metrics = evaluate_predictions(y_test, xgb_preds)

    # 6. Train Random Forest Classifier (Acute Exacerbation Risk in next 12m)
    exac_model = None
    exac_metrics = {}
    exac_importances = {}
    if y_train_exac is not None and len(y_train_exac.unique()) > 1:
        exac_model = RandomForestClassifier(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        )
        exac_model.fit(X_train_proc, y_train_exac)
        if y_test_exac is not None and len(y_test_exac.unique()) > 1:
            exac_preds = exac_model.predict(X_test_proc)
            exac_probs = exac_model.predict_proba(X_test_proc)[:, 1]
            try:
                roc_auc = float(roc_auc_score(y_test_exac, exac_probs))
            except Exception:
                roc_auc = 0.5
            exac_metrics = {
                "accuracy": round(float(accuracy_score(y_test_exac, exac_preds)), 4),
                "roc_auc": round(roc_auc, 4),
                "f1": round(float(f1_score(y_test_exac, exac_preds, zero_division=0)), 4),
            }
        feature_names_list = list(preprocessor.get_feature_names_out())
        exac_importances = {
            feat: round(float(imp), 4)
            for feat, imp in zip(feature_names_list, exac_model.feature_importances_)
        }

    # 7. Extract feature importances
    feature_names = list(preprocessor.get_feature_names_out())
    rf_importances = {
        feat: round(float(imp), 4)
        for feat, imp in zip(feature_names, rf_model.feature_importances_)
    }
    xgb_importances = {
        feat: round(float(imp), 4)
        for feat, imp in zip(feature_names, xgb_model.feature_importances_)
    }

    metadata = {
        "rf_metrics": rf_metrics,
        "xgb_metrics": xgb_metrics,
        "exac_metrics": exac_metrics,
        "rf_feature_importances": rf_importances,
        "xgb_feature_importances": xgb_importances,
        "exac_feature_importances": exac_importances,
        "feature_names": feature_names,
        "n_train_samples": len(X_train),
        "n_test_samples": len(X_test),
        "n_train_patients": train_df["patient_id"].nunique(),
        "n_test_patients": test_df["patient_id"].nunique(),
    }

    # 8. Persist artifacts
    if save_artifacts:
        target_dir = Path(artifacts_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        joblib.dump(preprocessor, target_dir / "preprocessor.joblib")
        joblib.dump(rf_model, target_dir / "rf_model.joblib")
        joblib.dump(xgb_model, target_dir / "xgb_model.joblib")
        if exac_model is not None:
            joblib.dump(exac_model, target_dir / "exac_classifier.joblib")
        joblib.dump(metadata, target_dir / "model_metadata.joblib")

        # Invalidate cache for this directory
        clear_model_cache(target_dir)

    return {
        "rf_model": rf_model,
        "xgb_model": xgb_model,
        "exac_model": exac_model,
        "preprocessor": preprocessor,
        "metrics": metadata,
        "train_df": train_df,
        "test_df": test_df,
    }


def clear_model_cache(artifacts_dir: Optional[Union[str, Path]] = None) -> None:
    """Clear the in-memory cache of loaded models and preprocessors."""
    global _MODEL_CACHE, _PREPROCESSOR_CACHE
    if artifacts_dir is None:
        _MODEL_CACHE.clear()
        _PREPROCESSOR_CACHE.clear()
    else:
        dir_str = str(Path(artifacts_dir).resolve())
        keys_to_remove = [k for k in _MODEL_CACHE if k[0] == dir_str]
        for k in keys_to_remove:
            del _MODEL_CACHE[k]
        if dir_str in _PREPROCESSOR_CACHE:
            del _PREPROCESSOR_CACHE[dir_str]


def load_model_artifacts(
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    model_type: str = "random_forest",
) -> Tuple[Any, Any]:
    """Load preprocessor and specified trained model from artifacts folder.

    Uses an in-memory cache to avoid repeated disk reads.

    Parameters
    ----------
    artifacts_dir : Union[str, Path], default='artifacts'
        Directory containing .joblib artifact files.
    model_type : str, default='random_forest'
        Model type to load: 'random_forest' (or 'rf') / 'xgboost' (or 'xgb').

    Returns
    -------
    preprocessor : ColumnTransformer
        Fitted scikit-learn preprocessor.
    model : Union[RandomForestRegressor, XGBRegressor]
        Trained regression model.
    """
    target_dir = Path(artifacts_dir).resolve()
    norm_type = model_type.lower().strip()

    if norm_type in ("random_forest", "rf"):
        model_filename = "rf_model.joblib"
        canonical_name = "random_forest"
    elif norm_type in ("xgboost", "xgb"):
        model_filename = "xgb_model.joblib"
        canonical_name = "xgboost"
    else:
        raise ValueError(
            f"Unsupported model_type: '{model_type}'. Expected 'random_forest' or 'xgboost'."
        )

    cache_key = (str(target_dir), canonical_name)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    preprocessor_path = target_dir / "preprocessor.joblib"
    model_path = target_dir / model_filename

    if not preprocessor_path.exists():
        raise FileNotFoundError(f"Preprocessor artifact not found at {preprocessor_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {model_path}")

    preprocessor = joblib.load(preprocessor_path)
    model = joblib.load(model_path)

    _MODEL_CACHE[cache_key] = (preprocessor, model)
    return preprocessor, model


def load_exac_classifier(
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
) -> Tuple[Any, Any]:
    """Load preprocessor and trained exacerbation RandomForestClassifier from artifacts.

    Uses an in-memory cache to avoid repeated disk reads.

    Parameters
    ----------
    artifacts_dir : Union[str, Path], default='artifacts'
        Directory containing .joblib artifact files.

    Returns
    -------
    preprocessor : ColumnTransformer
        Fitted scikit-learn preprocessor.
    classifier : RandomForestClassifier
        Trained exacerbation classifier.
    """
    target_dir = Path(artifacts_dir).resolve()
    cache_key = (str(target_dir), "exac_classifier")
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    preprocessor_path = target_dir / "preprocessor.joblib"
    classifier_path = target_dir / "exac_classifier.joblib"

    if not preprocessor_path.exists():
        raise FileNotFoundError(f"Preprocessor artifact not found at {preprocessor_path}")
    if not classifier_path.exists():
        raise FileNotFoundError(f"Exacerbation classifier artifact not found at {classifier_path}")

    preprocessor = joblib.load(preprocessor_path)
    classifier = joblib.load(classifier_path)

    _MODEL_CACHE[cache_key] = (preprocessor, classifier)
    return preprocessor, classifier


def predict_fev1(
    features: Union[pd.DataFrame, dict, list],
    model_type: str = "random_forest",
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    preprocessor: Optional[Any] = None,
    model: Optional[Any] = None,
    return_risk: bool = False,
) -> Union[float, np.ndarray, Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]]:
    """Predict lung function (`fev1_liters`) for one or more patient observations.

    Parameters
    ----------
    features : Union[pd.DataFrame, dict, list]
        Observation(s) containing the 9 approved inputs:
        age_at_visit, sex, gold_stage_baseline, smoking_status_at_visit,
        pack_years, activity_level_at_visit, bmi, months_since_baseline,
        baseline_fev1_liters.
    model_type : str, default='random_forest'
        'random_forest' (or 'rf') / 'xgboost' (or 'xgb').
    artifacts_dir : Union[str, Path], default='artifacts'
        Directory containing .joblib artifact files if model/preprocessor not passed.
    preprocessor : Optional[Any]
        Pre-loaded fitted ColumnTransformer (optional override).
    model : Optional[Any]
        Pre-loaded trained model (optional override).
    return_risk : bool, default=False
        If True, returns a tuple of (predicted_fev1, exacerbation_risk_pct).

    Returns
    -------
    predictions : Union[float, np.ndarray, Tuple[Any, Any]]
        Predicted FEV1 in liters (or tuple of (fev1, risk_pct) if return_risk is True).
    """
    is_single_dict = isinstance(features, dict)
    if is_single_dict:
        features_df = pd.DataFrame([features])
    elif isinstance(features, list):
        features_df = pd.DataFrame(features)
    elif isinstance(features, pd.DataFrame):
        features_df = features.copy()
    else:
        raise TypeError(f"Unsupported features type: {type(features)}. Expected DataFrame, dict, or list.")

    # Validate that all approved features are present
    missing = [c for c in APPROVED_FEATURES if c not in features_df.columns]
    if missing:
        raise KeyError(f"Input features missing required columns: {missing}")

    # Isolate strictly approved features to guard against downstream consequence leakage
    X = features_df[APPROVED_FEATURES].copy()

    # Load artifacts if not explicitly provided
    if preprocessor is None or model is None:
        loaded_preprocessor, loaded_model = load_model_artifacts(
            artifacts_dir=artifacts_dir,
            model_type=model_type,
        )
        preprocessor = preprocessor or loaded_preprocessor
        model = model or loaded_model

    # Transform features
    X_proc = preprocessor.transform(X)

    # Generate predictions
    predictions = model.predict(X_proc)

    if return_risk:
        try:
            _, classifier = load_exac_classifier(artifacts_dir=artifacts_dir)
            probs = classifier.predict_proba(X_proc)[:, 1]
            risk_pcts = np.round(probs * 100.0, 1)
        except Exception:
            risk_pcts = np.zeros(len(predictions))

        if is_single_dict:
            return float(predictions[0]), float(risk_pcts[0])
        return np.asarray(predictions, dtype=float), np.asarray(risk_pcts, dtype=float)

    if is_single_dict:
        return float(predictions[0])
    return np.asarray(predictions, dtype=float)


def predict_exacerbation_risk(
    features: Union[pd.DataFrame, dict, list],
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    preprocessor: Optional[Any] = None,
    classifier: Optional[Any] = None,
    as_pct: bool = True,
) -> Union[float, np.ndarray]:
    """Predict acute exacerbation probability within the next 12 months.

    Parameters
    ----------
    features : Union[pd.DataFrame, dict, list]
        Observation(s) with approved features.
    artifacts_dir : Union[str, Path], default='artifacts'
        Artifacts directory.
    preprocessor : Optional[Any]
        Optional preloaded preprocessor.
    classifier : Optional[Any]
        Optional preloaded RandomForestClassifier.
    as_pct : bool, default=True
        If True, returns percentage in [0.0, 100.0] rounded to 1 decimal.
        If False, returns raw probability in [0.0, 1.0].

    Returns
    -------
    Union[float, np.ndarray]
        Exacerbation probability or percentage.
    """
    is_single_dict = isinstance(features, dict)
    if is_single_dict:
        features_df = pd.DataFrame([features])
    elif isinstance(features, list):
        features_df = pd.DataFrame(features)
    elif isinstance(features, pd.DataFrame):
        features_df = features.copy()
    else:
        raise TypeError(f"Unsupported features type: {type(features)}. Expected DataFrame, dict, or list.")

    missing = [c for c in APPROVED_FEATURES if c not in features_df.columns]
    if missing:
        raise KeyError(f"Input features missing required columns: {missing}")

    X = features_df[APPROVED_FEATURES].copy()

    if preprocessor is None or classifier is None:
        loaded_preproc, loaded_clf = load_exac_classifier(artifacts_dir=artifacts_dir)
        preprocessor = preprocessor or loaded_preproc
        classifier = classifier or loaded_clf

    X_proc = preprocessor.transform(X)
    probs = classifier.predict_proba(X_proc)[:, 1]

    if as_pct:
        res = np.round(probs * 100.0, 1)
    else:
        res = probs

    if is_single_dict:
        return float(res[0])
    return np.asarray(res, dtype=float)


def predict_dual(
    features: Union[pd.DataFrame, dict, list],
    model_type: str = "random_forest",
    artifacts_dir: Union[str, Path] = DEFAULT_ARTIFACTS_DIR,
    preprocessor: Optional[Any] = None,
    model: Optional[Any] = None,
    classifier: Optional[Any] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Predict both FEV1 decline and acute exacerbation risk for patient observations.

    Parameters
    ----------
    features : Union[pd.DataFrame, dict, list]
        Observation(s) containing the 9 approved inputs.
    model_type : str, default='random_forest'
        Regression model for FEV1: 'random_forest' or 'xgboost'.
    artifacts_dir : Union[str, Path], default='artifacts'
        Directory with saved joblib models.

    Returns
    -------
    Union[Dict[str, Any], List[Dict[str, Any]]]
        For single observation:
        {
            "predicted_fev1_liters": 1.85,
            "exacerbation_risk_prob": 0.72,
            "exacerbation_risk_pct": 72.0,
            "risk_display": "72% risk",
            "model_used": model_type
        }
    """
    is_single_dict = isinstance(features, dict)
    if is_single_dict:
        features_df = pd.DataFrame([features])
    elif isinstance(features, list):
        features_df = pd.DataFrame(features)
    elif isinstance(features, pd.DataFrame):
        features_df = features.copy()
    else:
        raise TypeError(f"Unsupported features type: {type(features)}.")

    missing = [c for c in APPROVED_FEATURES if c not in features_df.columns]
    if missing:
        raise KeyError(f"Input features missing required columns: {missing}")

    X = features_df[APPROVED_FEATURES].copy()

    if preprocessor is None or model is None:
        preprocessor, model = load_model_artifacts(artifacts_dir=artifacts_dir, model_type=model_type)
    if classifier is None:
        _, classifier = load_exac_classifier(artifacts_dir=artifacts_dir)

    X_proc = preprocessor.transform(X)
    fev1_preds = model.predict(X_proc)
    exac_probs = classifier.predict_proba(X_proc)[:, 1]

    results = []
    for f_pred, e_prob in zip(fev1_preds, exac_probs):
        risk_pct = round(float(e_prob) * 100.0, 1)
        results.append({
            "predicted_fev1_liters": round(float(f_pred), 4),
            "exacerbation_risk_prob": round(float(e_prob), 4),
            "exacerbation_risk_pct": risk_pct,
            "risk_display": f"{int(round(risk_pct))}% risk",
            "model_used": model_type,
        })

    if is_single_dict:
        return results[0]
    return results


if __name__ == "__main__":
    raw_csv = Path("data/raw/copd_synthetic_longitudinal.csv")
    if raw_csv.exists():
        print(f"Loading raw longitudinal data from {raw_csv}...")
        raw_df = load_data(raw_csv)
        print(f"Loaded {len(raw_df)} rows. Training models with GroupShuffleSplit...")
        results = train_models(raw_df, artifacts_dir=DEFAULT_ARTIFACTS_DIR, save_artifacts=True)
        metrics = results["metrics"]
        print("\n--- Training Results (Held-out Patient Test Set) ---")
        print(f"Patients: {metrics['n_train_patients']} train / {metrics['n_test_patients']} test")
        print(f"Samples:  {metrics['n_train_samples']} train / {metrics['n_test_samples']} test")
        print(f"Random Forest -> MAE: {metrics['rf_metrics']['mae']}, RMSE: {metrics['rf_metrics']['rmse']}, R2: {metrics['rf_metrics']['r2']}")
        print(f"XGBoost       -> MAE: {metrics['xgb_metrics']['mae']}, RMSE: {metrics['xgb_metrics']['rmse']}, R2: {metrics['xgb_metrics']['r2']}")
        print(f"\nArtifacts successfully saved to {DEFAULT_ARTIFACTS_DIR.resolve()}")
    else:
        print(f"Data file not found at {raw_csv}")
