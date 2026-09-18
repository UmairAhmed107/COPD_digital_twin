# Architecture v2 — COPD Digital Twin (course project)

**This replaces the earlier architecture entirely.** No reliability-aware
Bayesian updating, no uncertainty tracking, no patent-novelty framing.

## One-line description

An interactive digital twin that maintains an evolving patient record,
uses a trained ML model to predict lung function, and lets you simulate
future trajectories and what-if interventions.

## The three demo layers

**Layer 1 — New patient prediction**
Enter patient characteristics → model predicts `fev1_liters` → show it →
edit an input → predict again. Demonstrates the model responding to input
changes.

**Layer 2 — Evolving twin**
Pick an existing patient → see their visit history and current twin state →
click "Add Visit" → enter a new observation → twin state updates → model
re-predicts → trajectory chart updates. Demonstrates that this is a
persistent, evolving record, not a one-shot classifier.

**Layer 3 — Simulation / what-if**
From the current twin state, run a future simulation: sweep time forward
under multiple scenarios (baseline / smoking cessation / increased
activity) and plot all trajectories on one chart. Also show a model
comparison (RF vs. XGBoost) with evaluation metrics.

## System diagram

```
        Patient Input / Add Visit
                  |
                  v
        ┌───────────────────┐
        │   Twin State       │   <- static baseline + latest visit + history
        │  (src/twin_state)  │      (no Bayesian/uncertainty machinery)
        └─────────┬──────────┘
                  |
                  v
        ┌───────────────────┐
        │   ML Pipeline       │
        │  preprocess         │
        │  RF / XGBoost        │
        │  predict fev1_liters │
        └─────────┬──────────┘
                  |
      ┌───────────┴───────────┐
      v                        v
Single prediction        Simulation (sweep months_since_baseline,
(Layer 1)                 optionally vary smoking/activity) (Layer 3)
      |                        |
      v                        v
        Dashboard (charts, comparisons, add-visit form)
```

## Twin state — deliberately simple

```
TwinState = {
  patient_id,
  static: {sex, age_at_baseline, gold_stage_baseline,
           smoking_status_baseline, pack_years, baseline_fev1_liters,
           baseline_fvc_liters, baseline_fev1_fvc_ratio, bmi},
  current: {latest visit's time-varying fields},
  history: [visit_1, visit_2, ..., visit_n]
}
```

"Add Visit" = append a new entry to `history` and set `current` to it. That
is the entire state-update mechanism — no smoothing, no weighting, no
versioning ceremony.

## ML model

- Target: `fev1_liters`
- Approved inputs: `age_at_visit`, `sex`, `gold_stage_baseline`,
  `smoking_status_at_visit`, `pack_years`, `activity_level_at_visit`,
  `bmi`, `months_since_baseline`, `baseline_fev1_liters`
- Excluded from inputs: `spo2_pct`, `cat_score` (downstream consequences,
  not causes — including them leaks the answer), `injected_issue`
  (grading-only)
- Two models trained and compared: Random Forest, XGBoost
- Metrics: MAE, RMSE, R² on a patient-level held-out test split

## Simulation mechanism

Given a twin state and a trained model:

```
for t in [0, 6, 12, 18, ..., 36] months:
    features = current_state_features with months_since_baseline = t
    (optionally: smoking_status_at_visit / activity_level_at_visit changed)
    prediction = model.predict(features)
    trajectory.append((t, prediction))
```

Run this once per scenario (baseline, quit smoking, increase activity) and
plot all trajectories together. This is what makes the what-if genuinely
model-driven rather than a guessed effect size.

## Viva-ready answers

- **"What is the digital twin?"** A persistent, per-patient record of
  static identity + current state + visit history that updates when a new
  observation is added.
- **"Isn't this just a prediction model?"** No — the model is one component
  called by the twin. Adding a visit updates the twin's state, and the
  twin's state is what feeds the model each time.
- **"How does the model know a patient will deteriorate?"** It learned the
  relationship between smoking status, activity level, severity, age, and
  FEV1 decline from the training data — it's a trained regressor, not a
  rule.
- **"What happens when an input changes?"** The changed twin state is
  re-run through the same trained model, producing a new prediction and,
  if simulating, a new trajectory.
