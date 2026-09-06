"""
data_prep.py

Data Ingestion and Preparation module.

Reference: notes/architecture.md, Section 4.2

Responsibilities (per architecture.md):
- Load source data.
- Validate columns and data types.
- Handle missing values.
- Normalize numerical variables where appropriate.
- Encode categorical variables.
- Attach timestamps to longitudinal observations.
- Validate observation ranges.
- Preserve the distinction between observed and synthetic values.
- Produce a consistent observation format for the Twin State Module.

STATUS: Implemented, dataset-agnostic.

No specific COPD dataset has been finalized yet (architecture.md,
Section 14 - Open Questions). Rather than hard-coding assumptions
about column names, units, or value ranges for a particular dataset,
this module works against a caller-supplied `DatasetSchema`. When a
dataset is chosen, a `DatasetSchema` describing its columns should be
defined (e.g. in a later notebook/script or a dedicated config
module) and passed into these functions -- nothing here should need
to change.

Design notes for reproducibility (architecture.md: "the preprocessing
pipeline must be reproducible"):
- Normalization and encoding functions always return the *fitted
  parameters* (means/stds, min/max, category->code mappings) used,
  in addition to the transformed data. Those fitted parameters can be
  passed back in on a later call to apply the exact same transform to
  new data, instead of silently refitting on a different sample.
- Missing-value handling never guesses or fabricates a value. It only
  flags missingness or drops incomplete rows -- both fully
  transparent, reversible-in-principle operations. Imputation
  strategies (mean/median/model-based fill-in) are intentionally NOT
  implemented here; deciding how to fill a missing physiological
  measurement is a modeling decision, not a data-preparation one, and
  must never happen silently.
- Timestamps are never fabricated. If the schema's timestamp column
  is absent or unparsable, this module raises rather than inventing a
  sequence.
- Real and synthetic data are kept explicitly distinguishable: every
  observation produced by `to_observation_format` carries an explicit
  `is_synthetic` flag and `source` label that the caller must supply;
  nothing is inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, Union

import pandas as pd

ColumnKind = Literal["numeric", "categorical", "boolean", "datetime"]

SUPPORTED_FILE_FORMATS = {"csv", "json"}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSpec:
    """
    Describes one expected data column.

    `valid_range` (numeric only) and `allowed_values` (categorical
    only) are optional. They should be supplied by the caller based
    on the specific dataset/domain knowledge being used -- this
    module does not assume any COPD-specific ranges or categories.
    """

    name: str
    kind: ColumnKind
    required: bool = True
    valid_range: Optional[tuple[float, float]] = None  # inclusive, numeric only
    allowed_values: Optional[tuple[Any, ...]] = None  # categorical only


@dataclass(frozen=True)
class DatasetSchema:
    """
    Caller-supplied description of a dataset's shape.

    `columns` should list the *observation value* columns (e.g.
    FEV1, SpO2, smoking_status) -- not the identifier or timestamp
    columns, which are declared separately via `patient_id_column`
    and `timestamp_column`.

    No default schema is provided anywhere in this module: a schema
    must always be constructed explicitly by the caller, so that no
    assumptions about a specific COPD dataset are baked in here.
    """

    columns: tuple[ColumnSpec, ...]
    patient_id_column: str
    timestamp_column: str

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> Optional[ColumnSpec]:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def numeric_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.kind == "numeric"]

    def categorical_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.kind == "categorical"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    column: Optional[str]
    row_index: Optional[int]
    issue_type: str
    message: str


@dataclass
class ValidationResult:
    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        self.is_valid = False


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_source_data(
    path: Union[str, Path], file_format: Optional[str] = None
) -> pd.DataFrame:
    """
    Load raw source data from `path` into a DataFrame.

    `file_format` may be given explicitly ("csv" or "json"); if
    omitted, it is inferred from the file extension. No specific
    COPD dataset is assumed -- this is a generic tabular loader.

    Raises FileNotFoundError if the path does not exist, and
    ValueError for an unsupported/unrecognized format.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source data file not found: {path}")

    fmt = (file_format or path.suffix.lstrip(".")).lower()
    if fmt not in SUPPORTED_FILE_FORMATS:
        raise ValueError(
            f"Unsupported file format '{fmt}'. Supported formats: "
            f"{sorted(SUPPORTED_FILE_FORMATS)}. Extend this loader "
            "explicitly once a specific COPD dataset/format is chosen."
        )

    if fmt == "csv":
        return pd.read_csv(path)
    if fmt == "json":
        return pd.read_json(path)
    raise AssertionError("unreachable: unhandled supported format")  # pragma: no cover


# ---------------------------------------------------------------------------
# Column / dtype validation
# ---------------------------------------------------------------------------


def validate_columns(data: pd.DataFrame, schema: DatasetSchema) -> ValidationResult:
    """
    Validate that `data` contains the columns declared in `schema`
    with plausibly-correct types. This does not mutate `data`.

    Checks performed:
    - patient ID and timestamp columns are present
    - each declared column is present (if `required`)
    - numeric columns contain numeric-coercible values
    - boolean columns contain boolean-like values
    - datetime columns contain parseable date/time values
    - categorical columns (if `allowed_values` is set) contain only
      allowed values
    """
    result = ValidationResult()

    if schema.patient_id_column not in data.columns:
        result.add(
            ValidationIssue(
                schema.patient_id_column,
                None,
                "missing_column",
                f"Patient ID column '{schema.patient_id_column}' is missing.",
            )
        )
    if schema.timestamp_column not in data.columns:
        result.add(
            ValidationIssue(
                schema.timestamp_column,
                None,
                "missing_column",
                f"Timestamp column '{schema.timestamp_column}' is missing.",
            )
        )

    bool_like = {True, False, 0, 1, "true", "false", "True", "False"}

    for col in schema.columns:
        if col.name not in data.columns:
            if col.required:
                result.add(
                    ValidationIssue(
                        col.name,
                        None,
                        "missing_column",
                        f"Required column '{col.name}' is missing.",
                    )
                )
            continue

        series = data[col.name]
        non_null = series.dropna()
        if non_null.empty:
            continue

        if col.kind == "numeric":
            coerced = pd.to_numeric(non_null, errors="coerce")
            if coerced.isna().any():
                result.add(
                    ValidationIssue(
                        col.name,
                        None,
                        "invalid_dtype",
                        f"Column '{col.name}' expected numeric values but "
                        "contains non-numeric entries.",
                    )
                )
        elif col.kind == "boolean":
            if not set(non_null.unique()).issubset(bool_like):
                result.add(
                    ValidationIssue(
                        col.name,
                        None,
                        "invalid_dtype",
                        f"Column '{col.name}' expected boolean-like values.",
                    )
                )
        elif col.kind == "datetime":
            parsed = pd.to_datetime(non_null, errors="coerce")
            if parsed.isna().any():
                result.add(
                    ValidationIssue(
                        col.name,
                        None,
                        "invalid_dtype",
                        f"Column '{col.name}' expected datetime values but "
                        "contains unparsable entries.",
                    )
                )
        elif col.kind == "categorical":
            if col.allowed_values is not None:
                invalid = set(non_null.unique()) - set(col.allowed_values)
                if invalid:
                    result.add(
                        ValidationIssue(
                            col.name,
                            None,
                            "invalid_category",
                            f"Column '{col.name}' contains values outside "
                            f"allowed_values: {sorted(map(str, invalid))}",
                        )
                    )

    return result


def validate_observation_ranges(
    data: pd.DataFrame, schema: DatasetSchema
) -> ValidationResult:
    """
    Flag numeric values that fall outside the `valid_range` declared
    for a column in the schema. Out-of-range values are reported as
    issues, not modified or removed -- the caller decides what to do
    with them (this module does not silently drop or "fix" data).
    """
    result = ValidationResult()

    for col in schema.columns:
        if col.kind != "numeric" or col.valid_range is None:
            continue
        if col.name not in data.columns:
            continue

        low, high = col.valid_range
        series = pd.to_numeric(data[col.name], errors="coerce")
        out_of_range = series.notna() & ((series < low) | (series > high))

        for idx in data.index[out_of_range]:
            result.add(
                ValidationIssue(
                    col.name,
                    int(idx),
                    "out_of_range",
                    f"Value {data.at[idx, col.name]!r} in column "
                    f"'{col.name}' is outside the declared valid range "
                    f"[{low}, {high}].",
                )
            )

    return result


# ---------------------------------------------------------------------------
# Missing values
# ---------------------------------------------------------------------------


@dataclass
class MissingValueReport:
    strategy: str
    missing_counts: dict[str, int]
    dropped_row_count: int = 0


_MISSING_VALUE_STRATEGIES = {"flag", "drop_rows"}


def handle_missing_values(
    data: pd.DataFrame, schema: DatasetSchema, strategy: str = "flag"
) -> tuple[pd.DataFrame, MissingValueReport]:
    """
    Handle missing values transparently.

    This function never guesses or fabricates a value for a missing
    observation. Supported strategies:

    - "flag" (default): leave missing values as NaN, and add a
      boolean "<column>_missing" indicator column for every declared
      schema column present in the data.
    - "drop_rows": drop rows that are missing any *required* schema
      column. No values are inferred or filled in.

    Any other strategy name raises ValueError. In particular,
    imputation strategies (mean/median/mode/model-based fill-in) are
    intentionally NOT implemented here.
    """
    if strategy not in _MISSING_VALUE_STRATEGIES:
        raise ValueError(
            f"Unknown missing-value strategy '{strategy}'. Supported: "
            f"{sorted(_MISSING_VALUE_STRATEGIES)}. Imputation strategies "
            "are intentionally not implemented in data_prep.py to avoid "
            "silently fabricating missing observations."
        )

    present_columns = [c.name for c in schema.columns if c.name in data.columns]
    missing_counts = {name: int(data[name].isna().sum()) for name in present_columns}

    working = data.copy()
    dropped = 0

    if strategy == "flag":
        for name in present_columns:
            working[f"{name}_missing"] = working[name].isna()
    else:  # "drop_rows"
        required_columns = [
            c.name for c in schema.columns if c.required and c.name in data.columns
        ]
        before = len(working)
        if required_columns:
            working = working.dropna(subset=required_columns)
        dropped = before - len(working)

    return working, MissingValueReport(
        strategy=strategy, missing_counts=missing_counts, dropped_row_count=dropped
    )


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


@dataclass
class NormalizationParams:
    method: str
    per_column: dict[str, dict[str, float]]


_NORMALIZATION_METHODS = {"zscore", "minmax"}


def normalize_numerical(
    data: pd.DataFrame,
    schema: DatasetSchema,
    method: str = "zscore",
    params: Optional[NormalizationParams] = None,
) -> tuple[pd.DataFrame, NormalizationParams]:
    """
    Normalize numeric columns declared in the schema.

    For reproducibility, the fitted parameters (mean/std for
    "zscore", min/max for "minmax") are always returned alongside the
    transformed data. Pass a previously-returned `NormalizationParams`
    back in via `params` to apply the *same* fitted transform to new
    data instead of refitting on it.
    """
    if method not in _NORMALIZATION_METHODS:
        raise ValueError(
            f"Unsupported normalization method '{method}'. Supported: "
            f"{sorted(_NORMALIZATION_METHODS)}."
        )

    working = data.copy()
    numeric_columns = [c for c in schema.numeric_columns() if c in data.columns]

    if params is not None:
        if params.method != method:
            raise ValueError(
                "Provided `params.method` "
                f"('{params.method}') does not match requested `method` "
                f"('{method}')."
            )
        fitted = params
    else:
        per_column: dict[str, dict[str, float]] = {}
        for col in numeric_columns:
            series = pd.to_numeric(working[col], errors="coerce")
            if method == "zscore":
                per_column[col] = {
                    "mean": float(series.mean(skipna=True)),
                    "std": float(series.std(skipna=True)),
                }
            else:  # minmax
                per_column[col] = {
                    "min": float(series.min(skipna=True)),
                    "max": float(series.max(skipna=True)),
                }
        fitted = NormalizationParams(method=method, per_column=per_column)

    for col in numeric_columns:
        if col not in fitted.per_column:
            continue
        series = pd.to_numeric(working[col], errors="coerce")
        stats = fitted.per_column[col]
        if method == "zscore":
            std = stats["std"]
            if not std or pd.isna(std):
                working[col] = series - stats["mean"]
            else:
                working[col] = (series - stats["mean"]) / std
        else:  # minmax
            span = stats["max"] - stats["min"]
            if not span or pd.isna(span):
                working[col] = 0.0
            else:
                working[col] = (series - stats["min"]) / span

    return working, fitted


# ---------------------------------------------------------------------------
# Categorical encoding
# ---------------------------------------------------------------------------


@dataclass
class EncodingMap:
    method: str
    mappings: dict[str, dict[str, int]]  # column -> {category(str): code}


_ENCODING_METHODS = {"label", "onehot"}


def encode_categorical(
    data: pd.DataFrame,
    schema: DatasetSchema,
    method: str = "label",
    encoding_map: Optional[EncodingMap] = None,
) -> tuple[pd.DataFrame, EncodingMap]:
    """
    Encode categorical columns declared in the schema.

    Supported methods:
    - "label" (default): integer codes. The fitted category->code
      mapping is always returned via `EncodingMap` for reproducibility,
      and can be passed back in via `encoding_map` to encode new data
      consistently with a previous fit.
    - "onehot": pandas dummy/indicator columns (via `pd.get_dummies`).
      Not currently reproducible via a returned mapping -- see the
      open decision noted in the module docstring/tests.
    """
    if method not in _ENCODING_METHODS:
        raise ValueError(
            f"Unsupported encoding method '{method}'. Supported: "
            f"{sorted(_ENCODING_METHODS)}."
        )

    working = data.copy()
    categorical_columns = [c for c in schema.categorical_columns() if c in data.columns]

    if method == "label":
        if encoding_map is not None:
            if encoding_map.method != "label":
                raise ValueError(
                    "Provided `encoding_map.method` "
                    f"('{encoding_map.method}') does not match requested "
                    f"`method` ('label')."
                )
            mappings = encoding_map.mappings
            fitted = encoding_map
        else:
            mappings = {}
            for col in categorical_columns:
                categories = sorted(working[col].dropna().unique().tolist(), key=str)
                mappings[col] = {str(cat): idx for idx, cat in enumerate(categories)}
            fitted = EncodingMap(method="label", mappings=mappings)

        for col in categorical_columns:
            col_map = mappings.get(col, {})
            working[col] = working[col].map(
                lambda v, m=col_map: m.get(str(v)) if pd.notna(v) else v
            )

    else:  # "onehot"
        if categorical_columns:
            working = pd.get_dummies(working, columns=categorical_columns, dummy_na=False)
        fitted = EncodingMap(method="onehot", mappings={})

    return working, fitted


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def attach_timestamps(data: pd.DataFrame, schema: DatasetSchema) -> pd.DataFrame:
    """
    Parse the timestamp column declared in the schema and sort
    observations chronologically per patient.

    This function does NOT fabricate timestamps. If the declared
    timestamp column is missing from `data`, this raises KeyError. If
    any non-null timestamp value cannot be parsed, this raises
    ValueError, naming the offending rows.
    """
    ts_col = schema.timestamp_column
    if ts_col not in data.columns:
        raise KeyError(
            f"Timestamp column '{ts_col}' declared in the schema is not "
            "present in the data. Timestamps are required for longitudinal "
            "observations and are never fabricated automatically."
        )

    working = data.copy()
    parsed = pd.to_datetime(working[ts_col], errors="coerce")

    unparsable = working[ts_col].notna() & parsed.isna()
    if unparsable.any():
        bad_rows = working.index[unparsable].tolist()
        raise ValueError(
            f"Timestamp column '{ts_col}' has unparsable values at row "
            f"indices: {bad_rows}"
        )

    working[ts_col] = parsed

    sort_columns = [c for c in (schema.patient_id_column, ts_col) if c in working.columns]
    if sort_columns:
        working = working.sort_values(by=sort_columns).reset_index(drop=True)

    return working


# ---------------------------------------------------------------------------
# Observation format
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    """
    Consistent observation format produced for the Twin State Module.

    `is_synthetic` and `source` are always explicit, caller-supplied
    values (see `to_observation_format`) -- never inferred -- so that
    real and synthetic observations remain clearly distinguishable
    downstream, per architecture.md Section 4.1.

    Reliability scoring is intentionally NOT computed here; that is
    the responsibility of reliability.py (not implemented in this
    step).
    """

    patient_id: Any
    timestamp: Any  # pandas.Timestamp (or NaT) after attach_timestamps
    values: dict[str, Any]
    is_synthetic: bool
    source: str


def to_observation_format(
    data: pd.DataFrame,
    schema: DatasetSchema,
    is_synthetic: bool,
    source: str,
) -> list[Observation]:
    """
    Convert a prepared DataFrame into a list of `Observation` records
    -- the consistent format expected by the Twin State Module.

    `is_synthetic` and `source` must be supplied explicitly for every
    call; this function never guesses whether data is real or
    synthetic (architecture.md Section 4.1).
    """
    if schema.patient_id_column not in data.columns:
        raise KeyError(
            f"Patient ID column '{schema.patient_id_column}' is not "
            "present in the data."
        )
    if schema.timestamp_column not in data.columns:
        raise KeyError(
            f"Timestamp column '{schema.timestamp_column}' is not "
            "present in the data."
        )
    if not source:
        raise ValueError("`source` must be a non-empty string identifying the data source.")

    value_columns = [
        c.name
        for c in schema.columns
        if c.name in data.columns
        and c.name not in (schema.patient_id_column, schema.timestamp_column)
    ]

    observations: list[Observation] = []
    for _, row in data.iterrows():
        values = {col: row[col] for col in value_columns}
        observations.append(
            Observation(
                patient_id=row[schema.patient_id_column],
                timestamp=row[schema.timestamp_column],
                values=values,
                is_synthetic=is_synthetic,
                source=source,
            )
        )
    return observations


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class PreparationResult:
    data: pd.DataFrame
    column_validation: ValidationResult
    range_validation: ValidationResult
    missing_value_report: MissingValueReport
    normalization_params: Optional[NormalizationParams]
    encoding_map: Optional[EncodingMap]
    observations: list[Observation]


def prepare_dataset(
    data: pd.DataFrame,
    schema: DatasetSchema,
    *,
    is_synthetic: bool,
    source: str,
    missing_value_strategy: str = "flag",
    normalize: bool = False,
    normalization_method: str = "zscore",
    normalization_params: Optional[NormalizationParams] = None,
    encode: bool = False,
    encoding_method: str = "label",
    encoding_map: Optional[EncodingMap] = None,
) -> PreparationResult:
    """
    Run the full, fixed, documented preparation pipeline:

        1. validate_columns
        2. validate_observation_ranges
        3. handle_missing_values
        4. (optional) normalize_numerical
        5. (optional) encode_categorical
        6. attach_timestamps
        7. to_observation_format

    All strategy choices are explicit keyword arguments -- there are
    no hidden defaults that fabricate or guess values. Validation
    issues (from steps 1-2) do not halt the pipeline; they are
    collected and returned in `PreparationResult` so the caller can
    inspect and decide how to act on them. This keeps the pipeline
    reproducible: given the same inputs and the same arguments (and,
    for repeat runs, the same `normalization_params`/`encoding_map`),
    it produces the same output.
    """
    column_validation = validate_columns(data, schema)
    range_validation = validate_observation_ranges(data, schema)

    working, missing_report = handle_missing_values(
        data, schema, strategy=missing_value_strategy
    )

    fitted_normalization = None
    if normalize:
        working, fitted_normalization = normalize_numerical(
            working, schema, method=normalization_method, params=normalization_params
        )

    fitted_encoding = None
    if encode:
        working, fitted_encoding = encode_categorical(
            working, schema, method=encoding_method, encoding_map=encoding_map
        )

    working = attach_timestamps(working, schema)

    observations = to_observation_format(
        working, schema, is_synthetic=is_synthetic, source=source
    )

    return PreparationResult(
        data=working,
        column_validation=column_validation,
        range_validation=range_validation,
        missing_value_report=missing_report,
        normalization_params=fitted_normalization,
        encoding_map=fitted_encoding,
        observations=observations,
    )
