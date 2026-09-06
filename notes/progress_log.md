# Progress Log — COPD Digital Twin

Append a dated entry after every significant development session.
Do not rewrite history — if an approach fails or changes, record the
change and why, per architecture.md Section 13 and novelty_notes.md
Section 18.

---

## 2026-09-02: Project scaffold created

**Change:** Created the initial project directory structure and
placeholder module files, per `architecture.md` Section 12.

**Reason:** Establish a working, testable project skeleton before
implementing any real logic, per project rule "build the simplest
working version first / one module at a time."

**What was created:**

- Directory structure: `data/{raw,processed,synthetic}`, `src/`,
  `dashboard/`, `tests/`, `notes/`.
- Placeholder modules (all stubs, no real logic, all raise
  `NotImplementedError` where a function is not yet implemented):
  - `src/data_prep.py`
  - `src/reliability.py`
  - `src/twin_state.py` (includes `StateVariable`, `TwinStateVersion`,
    and `TwinState` data structures matching architecture.md Section
    5.2 and 5.5, but no update logic)
  - `src/model.py`
  - `src/simulator.py`
  - `src/evaluation.py`
- Structural tests in `tests/` for each placeholder module, verifying
  imports succeed and stub functions clearly signal "not
  implemented."
- `requirements.txt` with only `pytest` (minimum needed at this
  stage).
- `README.md` describing project structure, rules, and setup.
- `pytest.ini` so tests can be run from the project root.

**What was explicitly NOT done (out of scope for this step):**

- No dataset chosen or loaded.
- No reliability calculation implemented.
- No twin state update mechanism implemented (baseline or proposed).
- No progression model implemented.
- No counterfactual simulator implemented.
- No dashboard implemented.
- No hardware integration.

**Expected effect:** A verifiable, importable, testable project
skeleton that later steps can build on incrementally.

**Experimental result:** `pytest` run from the project root passes
all structural tests (see verification command below).

**Relevant prior art checked:** None — this step is pure scaffolding,
not a technical mechanism.

**Next planned step (not yet started):** To be decided by the user.
Candidates per `architecture.md` Section 14 (Open Questions) include
finalizing a public dataset, then implementing `src/data_prep.py`
against that dataset.

---

## 2026-09-02 (session 2): src/data_prep.py implemented

**Change:** Implemented `src/data_prep.py` (previously a stub) with
working, dataset-agnostic data preparation logic, plus 28 new unit
tests in `tests/test_data_prep.py`.

**Reason:** Next planned step per session 1's log — implement the
data ingestion/preparation module per `architecture.md` Section 4.2,
one module at a time.

**What was implemented:**

- `ColumnSpec` / `DatasetSchema` — caller-supplied description of a
  dataset's columns (name, kind, required, valid_range,
  allowed_values) plus explicit `patient_id_column` /
  `timestamp_column`. No specific COPD dataset or column set is
  hard-coded anywhere; a schema must always be constructed explicitly
  by the caller.
- `load_source_data()` — generic CSV/JSON loader. Raises
  `FileNotFoundError` / `ValueError` rather than guessing formats.
- `validate_columns()` / `validate_observation_ranges()` — return a
  `ValidationResult` (list of `ValidationIssue`s) instead of a bare
  bool or raising, so callers can inspect problems without the
  pipeline halting or "auto-fixing" anything.
- `handle_missing_values()` — supports only `"flag"` (adds
  `<col>_missing` indicator columns, leaves NaN in place) and
  `"drop_rows"` (drops rows missing a required column). Any
  imputation strategy (mean/median/mode/model-based fill) is
  explicitly NOT implemented and raises `ValueError` if requested —
  this was a deliberate decision to satisfy the "do not silently
  fabricate missing data" rule.
- `normalize_numerical()` — z-score or min-max, returns fitted
  `NormalizationParams` (mean/std or min/max per column) so the exact
  same transform can be re-applied later (reproducibility).
- `encode_categorical()` — label encoding (returns a fitted
  `EncodingMap` for reuse) or one-hot (`pd.get_dummies`, not yet
  reproducible via a returned mapping — see open decisions below).
- `attach_timestamps()` — parses and sorts by the declared timestamp
  column per patient. Raises `KeyError`/`ValueError` rather than
  fabricating a timestamp if the column is missing or unparsable.
- `Observation` dataclass + `to_observation_format()` — produces the
  consistent observation format for the (not-yet-implemented) Twin
  State Module. `is_synthetic` and `source` are required, explicit,
  caller-supplied arguments on every call — never inferred.
- `prepare_dataset()` — orchestrates the above steps in a fixed,
  documented order; all strategy choices are explicit keyword
  arguments; validation issues are collected, not silently dropped.

**What was explicitly NOT done (out of scope for this step):**

- `reliability.py` was not touched (still a stub).
- `twin_state.py` was not touched (still a stub).
- No specific COPD dataset was chosen, downloaded, or assumed. All
  tests use small inline synthetic DataFrames constructed only for
  testing, explicitly not treated as a real or representative COPD
  dataset.
- No medical claims were added anywhere in code or docstrings.
- No imputation/fabrication of missing values or timestamps.
- `novelty_notes.md` was not modified.

**Dependency added:** `pandas>=2.0.0` (added to `requirements.txt`),
needed for generic tabular data handling. `pytest` remains the only
other dependency.

**Expected effect:** A working, reusable, schema-driven data
preparation pipeline that can be pointed at any future COPD dataset
once one is chosen, without needing to rewrite this module.

**Experimental result:** Full test suite run: 45/45 tests passed (17
pre-existing + 28 new). See verification command below.

**Relevant prior art checked:** None — this step implements a
generic data-preparation utility, not a technical mechanism under
patent investigation.

**Open decisions carried forward (not resolved, by design):**
1. One-hot encoding does not yet return a reproducible mapping the
   way label encoding does (e.g. to guarantee identical dummy columns
   are produced for later batches with a different observed category
   set). This should be revisited once a dataset/schema stabilizes.
2. The exact `DatasetSchema` for the eventual COPD dataset is
   undefined — deliberately left to be filled in once
   `architecture.md`'s "Finalize public dataset" open question is
   resolved.
3. Whether/how validation issues (`ValidationResult`) should feed
   into `reliability.py`'s reliability scoring is left for the
   `reliability.py` implementation step; `data_prep.py` only surfaces
   issues, it does not score or act on them.

**Next planned step (not yet started):** To be decided by the user.
Likely candidates: finalize a public dataset, or implement
`reliability.py` against the `ValidationResult`/`Observation` shapes
now available from this module.

---

## 2026-09-06 (session 3): Public dataset selected — no code changes

**Change:** Selected a candidate public COPD dataset and finalized
the mapping from its columns to twin-state fields. No implementation
code was written this session; this entry documents a design/data
decision only, per the requirement that every significant decision
be recorded even when no code changes.

**Reason:** `architecture.md` Section 14 lists "Finalize public
dataset" as an open question blocking `twin_state.py`
implementation. This was the next step per session 2's log.

**Dataset selected:** "COPD Patients Dataset" (Kaggle, uploader
prakharrathi25,
`https://www.kaggle.com/datasets/prakharrathi25/copd-student-dataset`).
101 patients, 24 columns.

**Provenance verification performed:** Confirmed via a peer-reviewed
publication (Zhang, Jiang, Wisselink et al., "A robust chronic
obstructive pulmonary disease classification model using dragonfly
optimized kernel extreme learning machine," *Scientific Reports*,
2025) which cites this same Kaggle dataset as its patient data
source, describing it as containing disease details of 101 COPD
patients across 24 factors (FVC, FEV1, atrial fibrillation, walking
ability, smoking habits, diabetes, hypertension, pack history, CAT
score, HAD, SGRQ, IHD). This confirms the dataset originates from
real clinical data rather than being purely synthetic or of unclear
origin, satisfying the "real vs. synthetic must be clearly
documented" requirement before use.

**Rejected candidate (same session):** An earlier Kaggle "COPD"
dataset was reviewed and rejected before this one. Reason for
rejection: no timestamp/visit structure (same limitation as the
selected dataset, not differentiating), a binary O2 flag instead of
a continuous SpO2 value (weaker than needed), and an ambiguous
unlabeled "Risk" target column with no clear definition available.
Recorded here per the "record failed approaches, do not silently
drop them" rule.

**Schema mapping decided (dataset column → twin-state field):**

*Static per-patient fields:*
- `ID` → `patient_id`
- `AGE` → `age` (`AGEquartiles` dropped — derivable from `age`)
- `gender` → `gender`
- `PackHistory`, `smoking` → `smoking_status`
- `Diabetes`, `hypertension`, `AtrialFib`, `IHD`, `muscular` →
  `comorbidities` (grouped)
- `COPDSEVERITY`, `copd` → `gold_stage` (retained as a ground-truth
  label, not treated as a state-update input)

*Real physiological/functional observations (ingested by
`twin_state.py` as updates):*
- `FEV1`, `FEV1PRED` → `fev1` (raw + percent-predicted)
- `FVC`, `FVCPRED` → `fvc` (raw + percent-predicted)
- `MWT1`, `MWT2`, `MWT1Best` → `walk_distance`
- `CAT` → `symptom_burden`
- `HAD` → `anxiety_depression`
- `SGRQ` → `quality_of_life`

*Synthetic fields (to be generated, not present in source data):*
- `spo2` — decision made this session to generate synthetic SpO2
  values rather than omit the variable, since `architecture.md`
  Section 5.2 lists SpO2 as a core state variable. Must be clearly
  labeled `is_synthetic=True` at the point of generation, consistent
  with the `Observation` dataclass contract already established in
  `data_prep.py`.
- Longitudinal visit timestamps and intermediate visit values for
  all fields above — required because the source dataset is
  cross-sectional (one row per patient at rehab-program intake), not
  longitudinal.

**Reliability-mechanism design decision:** `MWT1` and `MWT2` are two
independent real measurement attempts of the same walk-distance
observation. Decision: the discrepancy between `MWT1` and `MWT2` will
be used as a live input to `reliability.py`'s measurement-quality
component (closer agreement between attempts → higher measurement
reliability), rather than discarding the raw attempts and only
keeping `MWT1Best`. `MWT1Best` remains the value stored as the twin's
actual walk-distance state observation. This gives the reliability
mechanism a real (non-synthetic) demonstration case in addition to
its synthetic/noisy-data test scenarios.

**What was explicitly NOT done (out of scope for this session):**

- No code was written or modified. `data_prep.py`, `reliability.py`,
  and `twin_state.py` (stub) are unchanged from session 2.
- The dataset was not downloaded or loaded into the pipeline this
  session — only its column schema and provenance were reviewed.
- The synthetic longitudinal generation procedure (how many visits,
  what temporal spacing, what noise model) was not designed — remains
  an open decision.
- The synthetic SpO2 generation procedure (distribution, dependence
  on GOLD stage/other variables) was not designed — remains an open
  decision.
- `architecture.md` and `novelty_notes.md` were not modified.

**Expected effect:** Unblocks `twin_state.py` implementation by
resolving the dataset dependency noted in session 2's "next planned
step" and in `architecture.md` Section 14.

**Experimental result:** Not applicable — no code, no tests this
session.

**Relevant prior art checked:** None — dataset selection is not
itself a technical mechanism under patent investigation.

**Open decisions carried forward (not resolved, by design):**
1. Synthetic longitudinal visit generation procedure (visit count,
   spacing, noise/drift model) — deferred to `twin_state.py`
   implementation session.
2. Synthetic SpO2 generation procedure — deferred to `twin_state.py`
   implementation session.
3. One-hot encoding reproducibility gap in `data_prep.py` (carried
   forward from session 2, still unresolved).
4. Whether `data_prep.py`'s `ValidationResult` output feeds into
   `reliability.py` scoring (carried forward from session 2, still
   unresolved).
5. Small sample size (101 patients) — not a blocker, but noted as a
   constraint on how much weight later train/test-style experimental
   comparisons (architecture.md Section 8) can be given.

**Next planned step (not yet started):** Implement `src/twin_state.py`
— baseline update mechanisms first (simple replacement, exponential
smoothing), kept clearly separate from the proposed reliability-aware
Bayesian update mechanism, per `architecture.md` Section 5.4 and the
"one module per session" rule. A concrete `DatasetSchema` instance for
this dataset (per `data_prep.py`'s existing `DatasetSchema`/
`ColumnSpec` contract) should be defined as part of that session,
using the mapping above.

---

## Verification command for this session

Not applicable — no code changes this session.

For prior sessions' code:

```bash
cd copd-twin
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## 2026-09-06 (session 4): src/twin_state.py baseline mechanisms implemented

**Change:** Replaced the `twin_state.py` placeholder with a working
implementation of the two baseline update mechanisms from
`architecture.md` Section 5.4 (simple replacement, exponential
smoothing), plus 21 new unit tests in `tests/test_twin_state.py`. The
proposed reliability-aware Bayesian update mechanism (Section 5.3)
was intentionally NOT implemented in this session.

**Reason:** Next planned step per session 3's log, following
finalization of the dataset/schema mapping.

**Correction to prior understanding:** Before starting, the actual
`reliability.py` file was inspected and confirmed to still be a full
placeholder (every `assess_*`/`compute_reliability_score` function
raises `NotImplementedError`) -- contrary to an earlier (incorrect)
impression that it had been implemented. This session's `twin_state.py`
code does not depend on `reliability.py` in any way, so this did not
block the work, but `reliability.py` implementation remains a fully
open, unstarted step, not a completed one.

**Design decisions made this session:**

1. **Tracked variables are explicit, not inferred.** `TwinState` takes
   a `tracked_variables` sequence at construction (e.g. `["FEV1",
   "FVC", "MWT1Best", "CAT", "HAD", "SGRQ"]`). Static per-patient
   fields (age, gender, comorbidities, smoking status, GOLD stage)
   are out of scope for these incremental-update mechanisms -- they
   don't change per observation in the source dataset.
2. **MWT1/MWT2 (raw walk-test attempts) are not tracked state
   variables.** Per session 3's decision, they remain inputs to
   `reliability.py`'s future measurement-quality scoring; only
   `MWT1Best` is a candidate tracked variable.
3. **Neither baseline models uncertainty.** `StateVariable.uncertainty`
   is always `None` for baseline-produced versions -- modeling
   uncertainty in a principled way is reserved for distinguishing the
   proposed mechanism (architecture.md Section 5.3).
4. **Neither baseline uses a reliability score.**
   `TwinStateVersion.reliability_score` is always `None` for
   baseline-produced versions, consistent with `reliability.py` not
   being implemented and with reliability-weighting being specific to
   the proposed mechanism.
5. **Missing observation values are carried forward, never
   fabricated.** Both baselines keep the previous estimated value
   unchanged for a variable when the incoming observation is missing
   that value, rather than inventing a replacement. Verified by
   dedicated tests for both mechanisms.
6. **Timestamps may be `None`.** Following session 3's resolution of
   the "no timestamp column in the real dataset" gap (Option B: skip
   `data_prep.py`'s `attach_timestamps()` for the real baseline row
   rather than fabricate a date), `twin_state.py` treats `None`
   timestamps as a fully valid case throughout. A baseline
   `Observation` for this dataset should be constructed directly
   with `timestamp=None`; `data_prep.py` itself was not modified.

**What was implemented:**

- `StateVariable`, `TwinStateVersion` dataclasses (structure
  unchanged from the prior placeholder, matching architecture.md
  Section 5.2/5.5).
- `TwinState` class: `current_state()`, `_next_version_id()`,
  `_initial_state_values()` (shared first-observation handling for
  both mechanisms).
- `TwinState.update_baseline_replacement()` -- Baseline 1.
- `TwinState.update_baseline_exponential_smoothing()` -- Baseline 2,
  with explicit `alpha` parameter (default 0.3, validated to be in
  (0.0, 1.0], raises `ValueError` otherwise). Default is explicitly
  documented as an unvalidated placeholder, not a tuned value.
- `BASELINE_REPLACEMENT`, `BASELINE_EXPONENTIAL_SMOOTHING`,
  `PROPOSED_RELIABILITY_AWARE_BAYESIAN` (unused, defined only as a
  forward-reference label) constants so update-method history entries
  stay clearly labeled and distinguishable.
- `_is_missing()` helper using `pandas.isna`, consistent with
  `data_prep.py`'s missing-value conventions.

**What was explicitly NOT done (out of scope for this session):**

- Proposed reliability-aware Bayesian update mechanism -- not started.
- `reliability.py` -- not touched, still a placeholder.
- `data_prep.py` -- not touched (byte-for-byte verified unchanged).
- No real dataset was loaded. Tests use small, inline `Observation`
  instances (via `data_prep.py`'s `Observation` dataclass), the same
  convention `data_prep.py`'s own tests use -- explicitly not treated
  as a real or representative COPD dataset.
- Synthetic longitudinal visit generation procedure -- not designed
  or implemented this session; remains an open item.
- Synthetic SpO2 generation procedure -- not designed or implemented
  this session; remains an open item.
- No novelty claims added anywhere in code or docstrings; both
  mechanisms are explicitly labeled "baseline," consistent with
  novelty_notes.md Section 1 and Section 9.
- `architecture.md` and `novelty_notes.md` were not modified.

**Expected effect:** A working, dataset-agnostic pair of baseline
update mechanisms that `evaluation.py` can later compare against the
proposed mechanism once it exists, per architecture.md Section 8.

**Experimental result:** 21/21 new tests passed. Confirmed
`data_prep.py` and `reliability.py` are byte-identical to the
previously uploaded versions (no accidental cross-module edits).

**Relevant prior art checked:** None -- both mechanisms implemented
this session are standard, well-known baseline techniques
(last-value replacement, exponential smoothing), explicitly not
claimed as novel.

**Open decisions carried forward (not resolved, by design):**
1. Synthetic longitudinal visit generation procedure (visit count,
   spacing, noise/drift model) -- still undesigned.
2. Synthetic SpO2 generation procedure -- still undesigned.
3. One-hot encoding reproducibility gap in `data_prep.py` (carried
   forward from session 2, still unresolved).
4. Whether `data_prep.py`'s `ValidationResult` output feeds into
   `reliability.py` scoring (carried forward from session 2, still
   unresolved).
5. `reliability.py` implementation itself (all six components) --
   confirmed not started; needed before the proposed Bayesian
   mechanism can be built, since that mechanism is meant to consume
   reliability scores.
6. Exact `alpha` value for exponential smoothing -- placeholder
   (0.3) only, must be selected experimentally per architecture.md
   Section 8.
7. Final `tracked_variables` list for this dataset -- the session's
   examples (FEV1, FVC, MWT1Best, CAT, HAD, SGRQ, future synthetic
   SpO2) are illustrative; not yet locked as the official list to use
   when the real dataset is actually loaded.

**Next planned step (not yet started):** To be decided by the user.
Likely candidates: implement `reliability.py`'s six scoring
components (source reliability, measurement quality, temporal
consistency, physiological plausibility, historical consistency,
completeness), since the proposed reliability-aware Bayesian
mechanism in `twin_state.py` will need reliability scores as an
input; or design and implement the synthetic longitudinal visit /
synthetic SpO2 generation procedure.

---

## Verification command for this session

```bash
cd copd-twin
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/test_twin_state.py -v
```