"""Unit tests for COPD Digital Twin data preparation and preprocessing pipeline.

Validates data loading, cleaning, patient-level train/test splitting,
categorical encoding, and strict protection against feature leakage.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer

from src.data_prep import (
    APPROVED_FEATURES,
    CATEGORICAL_FEATURES,
    EXAC_TARGET_COL,
    EXCLUDED_LEAKAGE_COLS,
    NUMERIC_FEATURES,
    TARGET_COL,
    build_preprocessor,
    clean_data,
    get_features_and_both_targets,
    get_features_and_target,
    prepare_data,
    split_by_patient,
    verify_no_leakage,
)


def test_feature_leakage_guard(mock_dataset):
    """Ensure downstream consequences, targets, and grading keys are strictly excluded.

    STRICT CONSTRAINT: Drop `spo2_pct`, `cat_score`, and `injected_issue`
    from the feature set, as these are downstream consequences, not inputs.
    """
    X, y = get_features_and_target(mock_dataset)

    # 1. Verify strict prompt constraints
    for forbidden in ["spo2_pct", "cat_score", "injected_issue"]:
        assert (
            forbidden not in X.columns
        ), f"Feature leakage violation: '{forbidden}' found in feature matrix X!"

    # 2. Verify other downstream consequences and targets themselves are absent
    for downstream in ["fvc_liters", "fev1_fvc_ratio", TARGET_COL, EXAC_TARGET_COL]:
        assert (
            downstream not in X.columns
        ), f"Target or downstream consequence '{downstream}' found in feature matrix X!"

    # 3. Verify identifiers and visit metadata are absent
    for meta in [
        "patient_id",
        "visit_number",
        "smoking_status_baseline",
        "baseline_fvc_liters",
        "baseline_fev1_fvc_ratio",
        "exacerbations_this_visit",
        "exacerbation_in_next_12m",
        "measurement_source",
    ]:
        assert meta not in X.columns, f"Metadata column '{meta}' found in feature matrix X!"

    # 4. Verify feature set exactly matches the 9 approved input features
    assert list(X.columns) == APPROVED_FEATURES
    assert len(X.columns) == 9

    # 5. Verify target vector
    assert y.name == TARGET_COL
    assert len(y) == len(mock_dataset)
    pd.testing.assert_series_equal(y, mock_dataset[TARGET_COL])


def test_verify_no_leakage_raises_on_leakage(mock_dataset):
    """Ensure verify_no_leakage raises ValueError when forbidden columns exist."""
    # Passing raw mock_dataset containing spo2_pct, cat_score, injected_issue
    with pytest.raises(ValueError, match="Feature leakage detected"):
        verify_no_leakage(mock_dataset)

    # Passing dataframe with only target fev1_liters
    leaky_df = pd.DataFrame({"age_at_visit": [65.0], "fev1_liters": [1.5]})
    with pytest.raises(ValueError, match="Feature leakage detected"):
        verify_no_leakage(leaky_df)

    # Clean approved features should pass without error
    X, _ = get_features_and_target(mock_dataset)
    verify_no_leakage(X)  # Should not raise


def test_patient_level_split(mock_dataset):
    """Ensure train/test splitting is strictly by patient_id, never by row."""
    # mock_dataset has P0001 (2 visits) and P0002 (1 visit)
    train_df, test_df = split_by_patient(mock_dataset, test_size=0.5, random_state=42)

    assert len(train_df) > 0
    assert len(test_df) > 0

    train_pids = set(train_df["patient_id"])
    test_pids = set(test_df["patient_id"])

    # Patients must be completely disjoint
    assert train_pids.isdisjoint(
        test_pids
    ), "Longitudinal leakage: patient found in both train and test sets!"

    # All visits for patient P0001 must stay together
    p1_in_train = "P0001" in train_pids
    p1_in_test = "P0001" in test_pids
    assert p1_in_train != p1_in_test
    if p1_in_train:
        assert (train_df["patient_id"] == "P0001").sum() == 2
    else:
        assert (test_df["patient_id"] == "P0001").sum() == 2


def test_patient_level_split_validation():
    """Ensure split_by_patient raises error when patient_id is missing or insufficient."""
    df_missing_pid = pd.DataFrame({"age": [65, 70]})
    with pytest.raises(KeyError, match="patient_id"):
        split_by_patient(df_missing_pid)

    df_single_patient = pd.DataFrame({"patient_id": ["P0001", "P0001"]})
    with pytest.raises(ValueError, match="At least 2 unique patients"):
        split_by_patient(df_single_patient)


def test_clean_data_outlier_removal(mock_dataset):
    """Ensure clean_data handles injected_issue == 'outlier_fev1' and physiological bounds."""
    df_with_outlier = mock_dataset.copy()
    outlier_row = df_with_outlier.iloc[[0]].copy()
    outlier_row["injected_issue"] = "outlier_fev1"
    outlier_row["fev1_liters"] = 0.05  # Implausible low reading
    df_with_outlier = pd.concat([df_with_outlier, outlier_row], ignore_index=True)

    assert len(df_with_outlier) == 4

    # With drop_outliers=True, outlier should be dropped
    cleaned = clean_data(df_with_outlier, drop_outliers=True)
    assert len(cleaned) == 3
    assert "outlier_fev1" not in cleaned["injected_issue"].values

    # With drop_outliers=False, outlier should be retained
    not_cleaned = clean_data(df_with_outlier, drop_outliers=False)
    assert len(not_cleaned) == 4


def test_clean_data_missing_consequences(mock_dataset):
    """Ensure missing consequence values in spo2_pct / cat_score are cleanly imputed."""
    df_missing = mock_dataset.copy()
    df_missing.loc[0, "spo2_pct"] = np.nan
    df_missing.loc[1, "cat_score"] = np.nan

    cleaned = clean_data(df_missing, impute_consequences=True)
    assert not cleaned["spo2_pct"].isna().any()
    assert not cleaned["cat_score"].isna().any()


def test_build_preprocessor(mock_dataset):
    """Ensure build_preprocessor creates a working ColumnTransformer with pandas output."""
    X, _ = get_features_and_target(mock_dataset)
    preprocessor = build_preprocessor()

    assert isinstance(preprocessor, ColumnTransformer)

    X_proc = preprocessor.fit_transform(X)

    # Check transformed output properties
    assert isinstance(X_proc, pd.DataFrame)
    assert len(X_proc) == len(mock_dataset)

    # Check that all numeric features were preserved
    for num_col in NUMERIC_FEATURES:
        col_name = f"num__{num_col}"
        assert col_name in X_proc.columns
        np.testing.assert_allclose(X_proc[col_name].values, X[num_col].values)

    # Check that categorical features were one-hot encoded
    assert any("cat__sex_" in c for c in X_proc.columns)
    assert any("cat__smoking_status_at_visit_" in c for c in X_proc.columns)
    assert any("cat__activity_level_at_visit_" in c for c in X_proc.columns)


def test_preprocessor_handles_unseen_categories(mock_dataset):
    """Ensure preprocessor gracefully ignores unseen categories at inference time."""
    X, _ = get_features_and_target(mock_dataset)
    preprocessor = build_preprocessor()
    preprocessor.fit(X)

    # Create unseen inference input
    X_unseen = X.iloc[[0]].copy()
    X_unseen.loc[0, "smoking_status_at_visit"] = "rare_new_status"

    # Should transform without raising an unknown category error
    transformed = preprocessor.transform(X_unseen)
    assert len(transformed) == 1
    # The one-hot columns for smoking status should all be 0 for this unseen category
    smoking_cols = [c for c in transformed.columns if "cat__smoking_status_at_visit_" in c]
    for col in smoking_cols:
        assert transformed.loc[0, col] == 0.0


def test_prepare_data_pipeline(mock_dataset):
    """Ensure prepare_data executes the full pipeline end-to-end."""
    X_train, X_test, y_train, y_test, preprocessor = prepare_data(
        data_or_path=mock_dataset,
        test_size=0.5,
        random_state=42,
        drop_outliers=True,
    )

    assert isinstance(X_train, pd.DataFrame)
    assert isinstance(X_test, pd.DataFrame)
    assert isinstance(y_train, pd.Series)
    assert isinstance(y_test, pd.Series)

    assert len(X_train) == len(y_train)
    assert len(X_test) == len(y_test)
    assert len(X_train) + len(X_test) == len(mock_dataset)

    # Ensure no leakage in transformed columns
    for forbidden in EXCLUDED_LEAKAGE_COLS:
        for col in X_train.columns:
            assert forbidden not in col, f"Leakage column '{forbidden}' found in transformed features!"

    # Target column itself must never be among transformed features
    for col in X_train.columns:
        # Check that neither 'fev1_liters' nor 'num__fev1_liters' is in features (baseline_fev1_liters is allowed)
        feature_basename = col.split("__")[-1]
        assert feature_basename != TARGET_COL, f"Target column '{TARGET_COL}' leaked into feature matrix!"


def test_get_features_and_both_targets(mock_dataset):
    """Verify get_features_and_both_targets extracts approved features and both targets."""
    X, y_fev1, y_exac = get_features_and_both_targets(mock_dataset)

    assert list(X.columns) == APPROVED_FEATURES
    assert y_fev1.name == TARGET_COL
    assert y_exac is not None
    assert y_exac.name == EXAC_TARGET_COL
    assert len(y_exac) == len(mock_dataset)
    pd.testing.assert_series_equal(y_exac, mock_dataset[EXAC_TARGET_COL])


def test_prepare_data_with_exacerbation(mock_dataset):
    """Verify prepare_data returns both train and test targets when include_exac=True."""
    X_train, X_test, y_train, y_test, y_tr_ex, y_te_ex, preproc = prepare_data(
        data_or_path=mock_dataset,
        test_size=0.5,
        random_state=42,
        drop_outliers=True,
        include_exac=True,
    )

    assert isinstance(X_train, pd.DataFrame)
    assert isinstance(X_test, pd.DataFrame)
    assert isinstance(y_tr_ex, pd.Series)
    assert isinstance(y_te_ex, pd.Series)
    assert len(y_tr_ex) == len(X_train)
    assert len(y_te_ex) == len(X_test)
