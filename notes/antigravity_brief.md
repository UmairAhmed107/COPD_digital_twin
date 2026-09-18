# Antigravity Build Brief — COPD Digital Twin (v2)

Read this before writing any code. It supersedes any earlier brief for this
project — the earlier architecture (reliability-aware Bayesian state,
uncertainty, patent-novelty framing) is abandoned. Do not reintroduce it.

## What this project is

A course/academic demo, not a real clinical system and not a patent filing.
It will never be published or claimed as actually predicting COPD outcomes.
Say so explicitly in the README and any report text.

## What to build, in this order

1. **`src/data_prep.py`** — load `data/raw/copd_synthetic_longitudinal.csv`,
   clean it (handle missing `spo2_pct`/`cat_score`, decide how to treat the
   `injected_issue == outlier_fev1` rows), encode categoricals, output a
   clean feature table. See `notes/data_dictionary.md` for the full column
   spec — follow it exactly, especially which columns are valid model
   inputs.
2. **`src/model.py`** — train two real scikit-learn models (Random Forest and
   XGBoost) to predict `fev1_liters` from the approved feature list in
   `notes/data_dictionary.md`. Split train/test **by `patient_id`**, never by
   row. Report MAE, RMSE, and R² for both models side by side.
3. **`src/twin_state.py`** — deliberately simple. A patient's twin state is:
   their static baseline fields + their most recent visit's time-varying
   fields + the full visit history list. No Bayesian updating, no
   uncertainty tracking, no reliability weighting. "Add Visit" = append a
   new visit record and make it the current state.
4. **`src/simulator.py`** — given a twin state and a trained model:
   generate a trajectory by sweeping `months_since_baseline` forward
   (e.g. every 6 months, out to 3 years) and calling `model.predict()` at
   each step, holding other features fixed. A "what-if" scenario is the
   same sweep with one field changed (`smoking_status_at_visit` or
   `activity_level_at_visit`) before the model is called — never a
   hardcoded effect size.
5. **`api/`** (FastAPI) — endpoints per `notes/api_contract.md`.
6. **`dashboard/`** (Next.js/React) — three interaction layers per
   `notes/architecture.md`: new-patient prediction, patient history +
   add-visit, and simulation/what-if comparison.
7. **`src/evaluation.py`** — the RF-vs-XGBoost comparison table/plots.

## Hard constraints — do not violate

- No reliability-weighting, uncertainty modeling, or Bayesian state update.
  If you think one of these would "improve" the project, don't add it —
  flag it in `notes/progress_log.md` instead and move on.
- Never use `spo2_pct` or `cat_score` as inputs when predicting `fev1_liters`
  — they're downstream consequences in the synthetic data, not causes, and
  using them would leak the answer and produce misleadingly perfect metrics.
- Never use `injected_issue` as a model input — it's an answer key for
  grading the cleaning step only.
- Split train/test by `patient_id`, never by row.
- One module per session — don't touch a module that isn't part of the
  current task unless a genuine integration bug requires it.
- Log every non-trivial decision (which model won, why a cleaning choice was
  made, what was tried and rejected) to `notes/progress_log.md` with a date.

## Reference docs in this folder

- `architecture.md` — the full system design and the three demo layers
- `data_dictionary.md` — dataset columns and what each one means
- `api_contract.md` — REST endpoints the dashboard calls
- `progress_log.md` — dated session log, append after every session
