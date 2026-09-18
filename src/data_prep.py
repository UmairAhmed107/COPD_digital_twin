"""Data preparation and preprocessing pipeline for COPD Digital Twin.

Provides functions to load, clean, split, and encode synthetic longitudinal
COPD patient data for training predictive models of lung function (`fev1_liters`).
Guards strictly against feature leakage from downstream clinical consequences.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder

# --- Column Definitions per notes/data_dictionary.md ---

TARGET_COL = "fev1_liters"
EXAC_TARGET_COL = "exacerbation_in_next_12m"

# Strict constraint: Downstream consequences and grading keys MUST NEVER be features
EXCLUDED_LEAKAGE_COLS = [
    "spo2_pct",
    "cat_score",
    "injected_issue",
]

# Additional downstream consequences / metadata that should not be model predictors
OTHER_NON_FEATURE_COLS = [
    "fvc_liters",
    "fev1_fvc_ratio",
    "patient_id",
    "visit_number",
    "smoking_status_baseline",
    "baseline_fvc_liters",
    "baseline_fev1_fvc_ratio",
    "exacerbations_this_visit",
    "exacerbation_in_next_12m",
    "measurement_source",
]

# Approved 9 input features per notes/architecture.md and api/schemas.py (PredictRequest)
APPROVED_FEATURES = [
    "age_at_visit",
    "sex",
    "gold_stage_baseline",
    "smoking_status_at_visit",
    "pack_years",
    "activity_level_at_visit",
    "bmi",
    "months_since_baseline",
    "baseline_fev1_liters",
]

CATEGORICAL_FEATURES = [
    "sex",
    "gold_stage_baseline",
    "smoking_status_at_visit",
    "activity_level_at_visit",
]

NUMERIC_FEATURES = [
    "age_at_visit",
    "pack_years",
    "bmi",
    "months_since_baseline",
    "baseline_fev1_liters",
]


def load_data(filepath: Union[str, Path] = "data/raw/copd_synthetic_longitudinal.csv") -> pd.DataFrame:
    """Load raw synthetic longitudinal dataset from CSV."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found at: {path}")
    return pd.read_csv(path)


def clean_data(
    df: pd.DataFrame,
    drop_outliers: bool = True,
    impute_consequences: bool = True,
) -> pd.DataFrame:
    """Clean the longitudinal dataset.

    Parameters
    ----------
    df : pd.DataFrame
        Raw or partially processed dataset.
    drop_outliers : bool, default=True
        Whether to drop rows flagged as `outlier_fev1` or with physiologically
        implausible FEV1 readings (< 0.2L or > 6.0L).
    impute_consequences : bool, default=True
        Whether to impute missing values in descriptive consequence columns
        (`spo2_pct`, `cat_score`) for patient history/summary completeness.

    Returns
    -------
    pd.DataFrame
        Cleaned copy of the dataset.
    """
    cleaned = df.copy()

    # 1. Handle synthetic outliers
    if drop_outliers:
        if "injected_issue" in cleaned.columns:
            cleaned = cleaned[cleaned["injected_issue"] != "outlier_fev1"]
        if TARGET_COL in cleaned.columns:
            # Enforce broad physiological plausibility boundaries
            cleaned = cleaned[(cleaned[TARGET_COL] >= 0.2) & (cleaned[TARGET_COL] <= 6.0)]

    # 2. Handle missing consequence values if retaining full clinical record
    if impute_consequences:
        if "spo2_pct" in cleaned.columns and cleaned["spo2_pct"].isna().any():
            median_spo2 = cleaned["spo2_pct"].median()
            cleaned["spo2_pct"] = cleaned["spo2_pct"].fillna(median_spo2)
        if "cat_score" in cleaned.columns and cleaned["cat_score"].isna().any():
            median_cat = cleaned["cat_score"].median()
            cleaned["cat_score"] = cleaned["cat_score"].fillna(median_cat)

    return cleaned.reset_index(drop=True)


def verify_no_leakage(features_df: pd.DataFrame) -> None:
    """Verify that no leakage columns or downstream consequences exist in features.

    Raises
    ------
    ValueError
        If any leakage or target column is present in `features_df`.
    """
    forbidden_cols = set(EXCLUDED_LEAKAGE_COLS) | {
        TARGET_COL,
        EXAC_TARGET_COL,
        "fvc_liters",
        "fev1_fvc_ratio",
    }
    found = forbidden_cols.intersection(set(features_df.columns))
    if found:
        raise ValueError(
            f"Feature leakage detected! Forbidden columns found in feature set: {sorted(found)}"
        )


def get_features_and_target(
    df: pd.DataFrame,
    check_leakage: bool = True,
    return_exac: bool = False,
) -> Union[Tuple[pd.DataFrame, pd.Series], Tuple[pd.DataFrame, pd.Series, Optional[pd.Series]]]:
    """Separate approved features and target variable(s) from DataFrame.

    Strictly guards against feature leakage by:
    1. Explicitly dropping `spo2_pct`, `cat_score`, and `injected_issue`.
    2. Selecting strictly the 9 approved input features.
    3. Verifying that no leakage columns or targets remain in the feature set.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe containing visit records.
    check_leakage : bool, default=True
        Whether to assert that leakage columns are absent.
    return_exac : bool, default=False
        Whether to return the second target `exacerbation_in_next_12m` alongside FEV1.

    Returns
    -------
    If return_exac is False:
        X : pd.DataFrame
            Feature matrix containing only approved input features.
        y : pd.Series
            Target vector (`fev1_liters`).
    If return_exac is True:
        X : pd.DataFrame
            Feature matrix containing only approved input features.
        y : pd.Series
            Target vector (`fev1_liters`).
        y_exac : Optional[pd.Series]
            Binary classification target vector (`exacerbation_in_next_12m`).
    """
    # Explicitly drop leakage columns if present
    cols_to_drop = [c for c in EXCLUDED_LEAKAGE_COLS if c in df.columns]
    safe_df = df.drop(columns=cols_to_drop)

    # Isolate primary regression target variable
    if TARGET_COL not in df.columns:
        raise KeyError(f"Target column '{TARGET_COL}' not found in dataframe.")
    y = df[TARGET_COL].copy()

    # Isolate secondary classification target variable if available
    y_exac: Optional[pd.Series] = None
    if EXAC_TARGET_COL in df.columns:
        y_exac = df[EXAC_TARGET_COL].copy()

    # Extract approved features
    missing_approved = [c for c in APPROVED_FEATURES if c not in safe_df.columns]
    if missing_approved:
        raise KeyError(
            f"Missing approved feature columns in input dataframe: {missing_approved}"
        )

    X = safe_df[APPROVED_FEATURES].copy()

    if check_leakage:
        verify_no_leakage(X)

    if return_exac:
        return X, y, y_exac
    return X, y


def get_features_and_both_targets(
    df: pd.DataFrame,
    check_leakage: bool = True,
) -> Tuple[pd.DataFrame, pd.Series, Optional[pd.Series]]:
    """Convenience wrapper to extract features, FEV1 target, and exacerbation target."""
    return get_features_and_target(df, check_leakage=check_leakage, return_exac=True)


def split_by_patient(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset into train and test sets grouped by patient_id.

    Never splits visits of the same patient across train and test sets,
    preventing longitudinal data leakage.

    Parameters
    ----------
    df : pd.DataFrame
        Dataframe containing a `patient_id` column.
    test_size : float, default=0.2
        Fraction of patients to allocate to the test set.
    random_state : int, default=42
        Random seed for reproducibility.

    Returns
    -------
    train_df : pd.DataFrame
        Visits for training patients.
    test_df : pd.DataFrame
        Visits for test patients.
    """
    if "patient_id" not in df.columns:
        raise KeyError("Dataframe must contain 'patient_id' for patient-level split.")

    unique_patients = df["patient_id"].unique()
    if len(unique_patients) < 2:
        raise ValueError("At least 2 unique patients are required for patient-level split.")

    train_pids, test_pids = train_test_split(
        unique_patients,
        test_size=test_size,
        random_state=random_state,
    )

    train_df = df[df["patient_id"].isin(train_pids)].reset_index(drop=True)
    test_df = df[df["patient_id"].isin(test_pids)].reset_index(drop=True)

    # Sanity check: zero patient overlap
    overlap = set(train_df["patient_id"]).intersection(set(test_df["patient_id"]))
    if overlap:
        raise RuntimeError(f"Data split error: overlapping patient IDs found: {overlap}")

    return train_df, test_df


def build_preprocessor(
    categorical_features: Optional[List[str]] = None,
    numeric_features: Optional[List[str]] = None,
) -> ColumnTransformer:
    """Build a scikit-learn ColumnTransformer for encoding approved features.

    One-hot encodes categorical features and passes numeric features through.
    Sets pandas output transform so feature names are retained.

    Returns
    -------
    ColumnTransformer
        Configured preprocessor transformer.
    """
    cat_cols = categorical_features or CATEGORICAL_FEATURES
    num_cols = numeric_features or NUMERIC_FEATURES

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                cat_cols,
            ),
            (
                "num",
                "passthrough",
                num_cols,
            ),
        ],
        remainder="drop",
    )
    preprocessor.set_output(transform="pandas")
    return preprocessor


def prepare_data(
    data_or_path: Union[str, Path, pd.DataFrame] = "data/raw/copd_synthetic_longitudinal.csv",
    test_size: float = 0.2,
    random_state: int = 42,
    drop_outliers: bool = True,
    include_exac: bool = False,
) -> Union[
    Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, ColumnTransformer],
    Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, Optional[pd.Series], Optional[pd.Series], ColumnTransformer],
]:
    """Execute end-to-end data preparation pipeline.

    1. Load raw data (if file path passed) or use provided DataFrame.
    2. Clean data (handle outliers, impute consequence records).
    3. Split train/test by patient.
    4. Extract approved features and target(s), guarding against leakage.
    5. Fit ColumnTransformer on train features and transform both train and test.

    Returns
    -------
    If include_exac is False:
        X_train_proc, X_test_proc, y_train, y_test, preprocessor
    If include_exac is True:
        X_train_proc, X_test_proc, y_train, y_test, y_train_exac, y_test_exac, preprocessor
    """
    if isinstance(data_or_path, (str, Path)):
        raw_df = load_data(data_or_path)
    else:
        raw_df = data_or_path.copy()

    clean_df = clean_data(raw_df, drop_outliers=drop_outliers)
    train_df, test_df = split_by_patient(clean_df, test_size=test_size, random_state=random_state)

    if include_exac:
        X_train, y_train, y_train_exac = get_features_and_target(train_df, return_exac=True)
        X_test, y_test, y_test_exac = get_features_and_target(test_df, return_exac=True)
    else:
        X_train, y_train = get_features_and_target(train_df, return_exac=False)
        X_test, y_test = get_features_and_target(test_df, return_exac=False)
        y_train_exac, y_test_exac = None, None

    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    if include_exac:
        return X_train_proc, X_test_proc, y_train, y_test, y_train_exac, y_test_exac, preprocessor
    return X_train_proc, X_test_proc, y_train, y_test, preprocessor
