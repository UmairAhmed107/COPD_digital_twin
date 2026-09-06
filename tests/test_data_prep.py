"""
Unit tests for src/data_prep.py.

These tests use small, clearly-labeled synthetic DataFrames
constructed inline for testing purposes only -- they are NOT a COPD
dataset and no medical claims are made about the values used.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src import data_prep


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_schema(**overrides) -> data_prep.DatasetSchema:
    defaults = dict(
        columns=(
            data_prep.ColumnSpec(
                name="fev1", kind="numeric", required=True, valid_range=(0.0, 6.0)
            ),
            data_prep.ColumnSpec(
                name="spo2", kind="numeric", required=True, valid_range=(50.0, 100.0)
            ),
            data_prep.ColumnSpec(
                name="smoking_status",
                kind="categorical",
                required=False,
                allowed_values=("current", "former", "never"),
            ),
        ),
        patient_id_column="patient_id",
        timestamp_column="visit_date",
    )
    defaults.update(overrides)
    return data_prep.DatasetSchema(**defaults)


def make_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "patient_id": ["p1", "p1", "p2"],
            "visit_date": ["2026-01-01", "2026-02-01", "2026-01-15"],
            "fev1": [2.1, 2.0, 1.8],
            "spo2": [96.0, 95.0, 93.0],
            "smoking_status": ["former", "former", "current"],
        }
    )


# ---------------------------------------------------------------------------
# load_source_data
# ---------------------------------------------------------------------------


def test_load_source_data_csv(tmp_path):
    df = make_dataframe()
    csv_path = tmp_path / "synthetic_test_data.csv"
    df.to_csv(csv_path, index=False)

    loaded = data_prep.load_source_data(csv_path)

    assert list(loaded.columns) == list(df.columns)
    assert len(loaded) == len(df)


def test_load_source_data_missing_file_raises(tmp_path):
    missing_path = tmp_path / "does_not_exist.csv"
    with pytest.raises(FileNotFoundError):
        data_prep.load_source_data(missing_path)


def test_load_source_data_unsupported_format_raises(tmp_path):
    bad_path = tmp_path / "data.parquet"
    bad_path.write_text("not really parquet")
    with pytest.raises(ValueError):
        data_prep.load_source_data(bad_path)


# ---------------------------------------------------------------------------
# validate_columns
# ---------------------------------------------------------------------------


def test_validate_columns_passes_for_clean_data():
    schema = make_schema()
    df = make_dataframe()

    result = data_prep.validate_columns(df, schema)

    assert result.is_valid is True
    assert result.issues == []


def test_validate_columns_flags_missing_required_column():
    schema = make_schema()
    df = make_dataframe().drop(columns=["fev1"])

    result = data_prep.validate_columns(df, schema)

    assert result.is_valid is False
    assert any(issue.column == "fev1" for issue in result.issues)


def test_validate_columns_flags_non_numeric_value_in_numeric_column():
    schema = make_schema()
    df = make_dataframe()
    df["fev1"] = df["fev1"].astype(object)
    df.loc[0, "fev1"] = "not_a_number"

    result = data_prep.validate_columns(df, schema)

    assert result.is_valid is False
    assert any(
        issue.column == "fev1" and issue.issue_type == "invalid_dtype"
        for issue in result.issues
    )


def test_validate_columns_flags_disallowed_category():
    schema = make_schema()
    df = make_dataframe()
    df.loc[0, "smoking_status"] = "unknown_category"

    result = data_prep.validate_columns(df, schema)

    assert result.is_valid is False
    assert any(issue.column == "smoking_status" for issue in result.issues)


# ---------------------------------------------------------------------------
# validate_observation_ranges
# ---------------------------------------------------------------------------


def test_validate_observation_ranges_flags_out_of_range_value():
    schema = make_schema()
    df = make_dataframe()
    df.loc[0, "spo2"] = 150.0  # outside declared (50, 100) range

    result = data_prep.validate_observation_ranges(df, schema)

    assert result.is_valid is False
    assert any(
        issue.column == "spo2" and issue.issue_type == "out_of_range"
        for issue in result.issues
    )


def test_validate_observation_ranges_passes_for_in_range_values():
    schema = make_schema()
    df = make_dataframe()

    result = data_prep.validate_observation_ranges(df, schema)

    assert result.is_valid is True


# ---------------------------------------------------------------------------
# handle_missing_values
# ---------------------------------------------------------------------------


def test_handle_missing_values_flag_strategy_adds_indicator_and_keeps_nan():
    schema = make_schema()
    df = make_dataframe()
    df.loc[1, "fev1"] = None

    result_df, report = data_prep.handle_missing_values(df, schema, strategy="flag")

    assert "fev1_missing" in result_df.columns
    assert result_df.loc[1, "fev1_missing"] == True  # noqa: E712
    assert pd.isna(result_df.loc[1, "fev1"])  # value is NOT fabricated
    assert report.strategy == "flag"
    assert report.missing_counts["fev1"] == 1


def test_handle_missing_values_drop_rows_strategy_removes_incomplete_rows():
    schema = make_schema()
    df = make_dataframe()
    df.loc[1, "fev1"] = None  # fev1 is required

    result_df, report = data_prep.handle_missing_values(df, schema, strategy="drop_rows")

    assert len(result_df) == 2
    assert report.dropped_row_count == 1


def test_handle_missing_values_rejects_unknown_strategy():
    schema = make_schema()
    df = make_dataframe()

    with pytest.raises(ValueError):
        data_prep.handle_missing_values(df, schema, strategy="mean_impute")


def test_handle_missing_values_never_fabricates_a_value():
    """Explicit guard against silent imputation, per project rules."""
    schema = make_schema()
    df = make_dataframe()
    df.loc[0, "spo2"] = None

    result_df, _ = data_prep.handle_missing_values(df, schema, strategy="flag")

    # The missing value must still be missing -- not replaced with a
    # mean, zero, or any other guessed number.
    assert pd.isna(result_df.loc[0, "spo2"])


# ---------------------------------------------------------------------------
# normalize_numerical
# ---------------------------------------------------------------------------


def test_normalize_numerical_zscore_produces_zero_mean():
    schema = make_schema()
    df = make_dataframe()

    normalized, params = data_prep.normalize_numerical(df, schema, method="zscore")

    assert params.method == "zscore"
    assert "fev1" in params.per_column
    assert abs(normalized["fev1"].mean()) < 1e-9


def test_normalize_numerical_minmax_bounds_values_between_zero_and_one():
    schema = make_schema()
    df = make_dataframe()

    normalized, params = data_prep.normalize_numerical(df, schema, method="minmax")

    assert normalized["fev1"].min() == pytest.approx(0.0)
    assert normalized["fev1"].max() == pytest.approx(1.0)


def test_normalize_numerical_reapplies_previously_fitted_params():
    """Reproducibility: refitting must not occur when params are passed in."""
    schema = make_schema()
    df = make_dataframe()

    _, fitted_params = data_prep.normalize_numerical(df, schema, method="zscore")

    new_df = df.copy()
    new_df.loc[0, "fev1"] = 5.9  # a very different value

    reapplied, params_used = data_prep.normalize_numerical(
        new_df, schema, method="zscore", params=fitted_params
    )

    assert params_used is fitted_params
    expected = (5.9 - fitted_params.per_column["fev1"]["mean"]) / fitted_params.per_column[
        "fev1"
    ]["std"]
    assert reapplied.loc[0, "fev1"] == pytest.approx(expected)


def test_normalize_numerical_rejects_unsupported_method():
    schema = make_schema()
    df = make_dataframe()

    with pytest.raises(ValueError):
        data_prep.normalize_numerical(df, schema, method="robust_scaling")


# ---------------------------------------------------------------------------
# encode_categorical
# ---------------------------------------------------------------------------


def test_encode_categorical_label_encoding_is_deterministic():
    schema = make_schema()
    df = make_dataframe()

    encoded, mapping = data_prep.encode_categorical(df, schema, method="label")

    assert mapping.method == "label"
    codes = set(mapping.mappings["smoking_status"].values())
    assert codes == {0, 1}  # "current" and "former" in this sample
    assert encoded["smoking_status"].isin(codes).all()


def test_encode_categorical_reapplies_previous_mapping():
    schema = make_schema()
    df = make_dataframe()

    _, fitted_map = data_prep.encode_categorical(df, schema, method="label")

    new_row = pd.DataFrame(
        {
            "patient_id": ["p3"],
            "visit_date": ["2026-03-01"],
            "fev1": [2.2],
            "spo2": [97.0],
            "smoking_status": ["former"],
        }
    )

    reapplied, map_used = data_prep.encode_categorical(
        new_row, schema, method="label", encoding_map=fitted_map
    )

    assert map_used is fitted_map
    assert reapplied.loc[0, "smoking_status"] == fitted_map.mappings["smoking_status"]["former"]


def test_encode_categorical_onehot_creates_dummy_columns():
    schema = make_schema()
    df = make_dataframe()

    encoded, _ = data_prep.encode_categorical(df, schema, method="onehot")

    assert "smoking_status" not in encoded.columns
    assert any(c.startswith("smoking_status_") for c in encoded.columns)


# ---------------------------------------------------------------------------
# attach_timestamps
# ---------------------------------------------------------------------------


def test_attach_timestamps_parses_and_sorts():
    schema = make_schema()
    df = make_dataframe()

    result = data_prep.attach_timestamps(df, schema)

    assert pd.api.types.is_datetime64_any_dtype(result["visit_date"])
    # p1's two visits should be in chronological order
    p1_rows = result[result["patient_id"] == "p1"]
    assert list(p1_rows["visit_date"]) == sorted(p1_rows["visit_date"])


def test_attach_timestamps_missing_column_raises():
    schema = make_schema()
    df = make_dataframe().drop(columns=["visit_date"])

    with pytest.raises(KeyError):
        data_prep.attach_timestamps(df, schema)


def test_attach_timestamps_unparsable_value_raises():
    schema = make_schema()
    df = make_dataframe()
    df.loc[0, "visit_date"] = "not_a_date"

    with pytest.raises(ValueError):
        data_prep.attach_timestamps(df, schema)


def test_attach_timestamps_does_not_fabricate_missing_timestamp():
    """Rows with a genuinely missing timestamp must remain missing (NaT),
    never filled in with a guessed date."""
    schema = make_schema()
    df = make_dataframe()
    df.loc[0, "visit_date"] = None

    result = data_prep.attach_timestamps(df, schema)

    assert result["visit_date"].isna().any()


# ---------------------------------------------------------------------------
# to_observation_format
# ---------------------------------------------------------------------------


def test_to_observation_format_produces_expected_records():
    schema = make_schema()
    df = data_prep.attach_timestamps(make_dataframe(), schema)

    observations = data_prep.to_observation_format(
        df, schema, is_synthetic=True, source="unit_test_fixture"
    )

    assert len(observations) == 3
    first = observations[0]
    assert first.is_synthetic is True
    assert first.source == "unit_test_fixture"
    assert "fev1" in first.values
    assert "patient_id" not in first.values  # excluded: it's the identifier, not a value
    assert "visit_date" not in first.values  # excluded: it's the timestamp, not a value


def test_to_observation_format_distinguishes_real_and_synthetic():
    schema = make_schema()
    df = data_prep.attach_timestamps(make_dataframe(), schema)

    real_obs = data_prep.to_observation_format(
        df, schema, is_synthetic=False, source="clinic_export"
    )
    synthetic_obs = data_prep.to_observation_format(
        df, schema, is_synthetic=True, source="synthetic_generator"
    )

    assert all(o.is_synthetic is False for o in real_obs)
    assert all(o.is_synthetic is True for o in synthetic_obs)


def test_to_observation_format_requires_explicit_source():
    schema = make_schema()
    df = data_prep.attach_timestamps(make_dataframe(), schema)

    with pytest.raises(ValueError):
        data_prep.to_observation_format(df, schema, is_synthetic=True, source="")


def test_to_observation_format_missing_patient_id_column_raises():
    schema = make_schema()
    df = data_prep.attach_timestamps(make_dataframe(), schema).drop(columns=["patient_id"])

    with pytest.raises(KeyError):
        data_prep.to_observation_format(df, schema, is_synthetic=True, source="unit_test")


# ---------------------------------------------------------------------------
# prepare_dataset (orchestration)
# ---------------------------------------------------------------------------


def test_prepare_dataset_end_to_end_produces_observations():
    schema = make_schema()
    df = make_dataframe()

    result = data_prep.prepare_dataset(
        df,
        schema,
        is_synthetic=True,
        source="unit_test_pipeline",
        missing_value_strategy="flag",
    )

    assert result.column_validation.is_valid is True
    assert result.range_validation.is_valid is True
    assert len(result.observations) == 3
    assert all(o.is_synthetic for o in result.observations)


def test_prepare_dataset_reports_validation_issues_without_halting():
    schema = make_schema()
    df = make_dataframe()
    df.loc[0, "spo2"] = 999.0  # out of range, but pipeline should still complete

    result = data_prep.prepare_dataset(
        df, schema, is_synthetic=True, source="unit_test_pipeline"
    )

    assert result.range_validation.is_valid is False
    assert len(result.observations) == 3  # pipeline still produced output


def test_prepare_dataset_with_normalization_and_encoding_enabled():
    schema = make_schema()
    df = make_dataframe()

    result = data_prep.prepare_dataset(
        df,
        schema,
        is_synthetic=True,
        source="unit_test_pipeline",
        normalize=True,
        encode=True,
    )

    assert result.normalization_params is not None
    assert result.encoding_map is not None
    # encoded smoking_status values should now be present in observation values
    values = result.observations[0].values
    assert isinstance(values["smoking_status"], (int, float))
