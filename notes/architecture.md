# Architecture — AI-Based Digital Twin for COPD Progression & Personalized Care

**Status:** Draft v2 — living document, update every session  
**Last updated:** 2 September 2026

---

## 1. Problem Statement

Current COPD monitoring is episodic — patients see a doctor every few months, spirometry (FEV1/FVC) is measured mainly at clinic visits, and exacerbations may be detected only after they have started. There is no continuously updated, patient-specific model of how an individual's disease state is evolving between visits, and no system that lets a clinician or patient simulate "what if" this patient's treatment or behavior changes.

The project aims to investigate a software-based digital twin that maintains a persistent representation of an individual's respiratory state, updates that state as new heterogeneous observations arrive, predicts progression, and enables controlled counterfactual simulations.

---

## 2. What We're Building

A software system that:

1. Maintains a **persistent digital representation ("twin state")** of one patient's respiratory health.
2. Updates that state when new data arrives, rather than recomputing the entire patient representation from scratch.
3. Accepts heterogeneous data sources such as:
   - baseline clinical measurements
   - spirometry
   - SpO2
   - activity data
   - smoking status
4. Associates incoming observations with data-quality and reliability information.
5. Maintains both the estimated patient state and an associated measure of uncertainty.
6. Predicts progression from the current twin state.
7. Creates counterfactual branches of the twin state for hypothetical interventions.
8. Compares projected trajectories between the baseline and counterfactual scenarios.
9. Provides a dashboard showing the current state, historical trajectory, predicted progression, uncertainty, and simulation results.

The system is intended as a research prototype and demonstration, **not a medical diagnostic or treatment system**.

---

## 3. System Architecture

```text
┌─────────────────────────┐
│       Data Sources      │
│                         │
│ - Baseline clinical     │
│ - Spirometry            │
│ - SpO2                  │
│ - Activity              │
│ - Smoking status        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│    Data Ingestion &     │
│       Preparation       │
│                         │
│ - Cleaning              │
│ - Normalization         │
│ - Missing values        │
│ - Validation            │
│ - Timestamp handling    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Observation Quality &   │
│ Reliability Assessment  │
│                         │
│ - Source information    │
│ - Measurement quality   │
│ - Temporal consistency  │
│ - Physiological         │
│   plausibility          │
│ - Historical reliability│
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│      TWIN STATE         │
│       MODULE            │
│                         │
│ - Patient state vector  │
│ - State uncertainty     │
│ - Temporal information  │
│ - Reliability state     │
│ - Update history        │
│                         │
│ CORE TECHNICAL AREA     │
│ UNDER INVESTIGATION     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│    Progression Model    │
│                         │
│ - FEV1 trajectory       │
│ - Risk prediction       │
│ - Future state estimate │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Counterfactual Simulator │
│                         │
│ - Clone current state   │
│ - Apply intervention    │
│ - Propagate state       │
│ - Project trajectory    │
│ - Compare scenarios     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│       Dashboard         │
│                         │
│ - Current twin state    │
│ - Confidence/uncertainty│
│ - Historical trend      │
│ - Predicted trajectory  │
│ - What-if comparison    │
└─────────────────────────┘
```

---

## 4. System Components

### 4.1 Data Sources

Planned implementation order:

- [ ] Public COPD dataset for initial development
- [ ] Synthetic longitudinal patient observations
- [ ] Simulated sensor observations
- [ ] Optional ESP32 + pulse oximeter demonstration

The initial public dataset may be cross-sectional. Synthetic longitudinal data will therefore be used to demonstrate state updates over time.

Real measurements and synthetic measurements must always be clearly distinguished in the code and documentation.

---

### 4.2 Data Ingestion and Preparation

File:

```text
data_prep.py
```

Responsibilities:

- Load source data.
- Validate columns and data types.
- Handle missing values.
- Normalize numerical variables where appropriate.
- Encode categorical variables.
- Attach timestamps to longitudinal observations.
- Validate observation ranges.
- Preserve the distinction between observed and synthetic values.
- Produce a consistent observation format for the Twin State Module.

The preprocessing pipeline must be reproducible.

---

### 4.3 Observation Quality and Reliability Assessment

File:

```text
reliability.py
```

This module evaluates the reliability of each incoming observation before it is incorporated into the twin.

Candidate inputs to the reliability calculation include:

- data source
- measurement quality
- temporal consistency
- physiological plausibility
- consistency with the patient's historical observations
- availability/completeness of the observation

The exact reliability calculation is **not yet finalized** and must be experimentally evaluated.

The system should record:

```text
observation
source
quality information
reliability score
timestamp
reason/metadata
```

The reliability score should influence how strongly the observation affects the twin state.

---

## 5. Twin State Module

File:

```text
twin_state.py
```

### 5.1 Purpose

The Twin State Module maintains a persistent, versioned representation of the patient's current respiratory condition.

The state is updated incrementally when new observations arrive.

It must not simply replace the previous state with the latest observation.

---

### 5.2 Initial State Representation

The initial state may contain variables such as:

```text
FEV1
FVC
FEV1/FVC
SpO2
activity level
smoking status
exacerbation history
age
time since previous observation
```

The final state variables will be determined during implementation and experimentation.

Each state variable should support, where applicable:

```text
estimated value
uncertainty/confidence
timestamp
historical information
```

---

### 5.3 Proposed Initial Update Mechanism

The primary mechanism under investigation is:

**Reliability-aware Bayesian state updating.**

Conceptually:

```text
Previous Twin State
        +
Incoming Observation
        +
Observation Reliability
        ↓
State Update
        ↓
Updated Twin State
        +
Updated Uncertainty
```

The exact mathematical formulation must be specified in the implementation documentation after experimentation.

The mechanism must be compared against simpler baseline approaches.

---

### 5.4 Baseline Update Mechanisms

Before evaluating the proposed mechanism, implement at least one baseline:

1. Simple replacement/update.
2. Exponential smoothing.

The purpose is to determine whether the proposed mechanism provides measurable advantages when observations contain:

- noise
- missing values
- conflicting measurements
- anomalous observations
- observations from different sources

---

### 5.5 Twin State History

Every update should be recorded.

Example:

```text
Patient
│
├── State v1
│
├── State v2
│
├── State v3
│
└── State v4
```

Each version should contain:

```text
timestamp
state values
uncertainty
incoming observation
observation source
reliability score
update method/version
```

This allows the trajectory of the twin to be reproduced and inspected.

---

## 6. Progression Model

File:

```text
model.py
```

The progression model uses the current twin state to estimate future disease-related trajectories.

Initial targets may include:

- FEV1 decline
- future respiratory state
- exacerbation-related risk

Initial model:

```text
Random Forest / XGBoost
```

The model should first be implemented as a baseline before considering more complex temporal neural networks.

The progression model is **not the primary novelty target**.

Its primary role is to demonstrate that the maintained twin state can be used as an input representation for future prediction.

---

## 7. Counterfactual Simulator

File:

```text
simulator.py
```

### 7.1 Purpose

The simulator creates hypothetical branches from the current twin state.

Example:

```text
Current Twin
     │
     ├─────────────── Baseline future
     │
     ├─────────────── Improved adherence
     │
     ├─────────────── Smoking cessation
     │
     └─────────────── Increased activity
```

---

### 7.2 Simulation Process

Initial implementation:

```text
1. Obtain current twin state.
2. Create a copy of the state.
3. Apply a defined intervention.
4. Propagate the modified state through the progression model.
5. Generate a future trajectory.
6. Compare it with the baseline trajectory.
```

The system must preserve the original twin state when generating a counterfactual branch.

---

### 7.3 Counterfactual Mechanism Under Investigation

The simulator should eventually define:

- which state variables may be changed
- permitted intervention ranges
- how intervention changes are represented
- how changes propagate through future states
- how interactions between variables are handled
- how different scenarios are compared

These details are **not yet finalized** and must be documented after implementation.

---

## 8. Experimental Validation

The project must not rely only on a working demonstration.

We will compare at least:

```text
Baseline/static ML
        VS
Simple Twin State
        VS
Proposed Reliability-Aware Twin
```

Testing should include controlled conditions such as:

- clean observations
- noisy observations
- missing observations
- conflicting observations
- different observation sources
- anomalous observations

Potential evaluation measures include:

- state estimation error
- prediction error
- robustness to noisy observations
- robustness to missing observations
- trajectory consistency
- uncertainty calibration where measurable

The exact evaluation metrics will be selected according to the available dataset and implemented models.

The purpose is to determine whether the proposed mechanism produces a measurable technical improvement rather than merely providing a different implementation.

---

## 9. Patent/Novelty Development

This section is for technical documentation only and is **not a patent claim or legal conclusion**.

The primary technical mechanism under investigation is:

> A persistent patient-specific state representation that is incrementally updated from heterogeneous longitudinal observations using observation reliability information, while maintaining uncertainty and historical state information.

Potential technical areas to investigate:

1. Reliability-aware state updating.
2. Patient-specific historical reliability.
3. Heterogeneous data fusion.
4. Handling conflicting observations.
5. State uncertainty.
6. Temporal consistency.
7. Counterfactual state branching and propagation.
8. Real-time sensor-to-twin update pipeline.

No feature should be described as novel merely because it has been implemented. Prior-art research is required.

---

## 10. Prior-Art Research

Prior-art research must be performed before finalizing any patent language.

Search areas include:

```text
"digital twin" + COPD
"digital twin" + respiratory disease
"digital twin" + chronic disease
"patient state" + Bayesian update
"patient digital twin" + sensor fusion
"confidence weighted" + patient monitoring
"reliability weighted" + sensor fusion
"medical digital twin" + uncertainty
```

Relevant patents, papers and systems should be recorded in `novelty_notes.md`.

For every important prior-art reference, record:

```text
date found
title
publication/patent number
source
technical mechanism
overlap
difference
remaining technical gap
```

---

## 11. Dashboard

Initial dashboard requirements:

- Patient identifier
- Current twin state
- State uncertainty/confidence
- Historical state trajectory
- Incoming observations
- Reliability scores
- Predicted progression
- Counterfactual scenarios
- Baseline vs simulated trajectory

The dashboard is primarily for demonstration and visualization and is not the primary novelty target.

---

## 12. Project Structure

```text
copd-twin/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── synthetic/
│
├── src/
│   ├── data_prep.py
│   ├── reliability.py
│   ├── twin_state.py
│   ├── model.py
│   ├── simulator.py
│   └── evaluation.py
│
├── dashboard/
│
├── tests/
│
├── notes/
│   ├── architecture.md
│   ├── novelty_notes.md
│   └── progress_log.md
│
├── requirements.txt
└── README.md
```

---

## 13. Development Principles

1. Build the simplest working version first.
2. Do not implement the entire system in one step.
3. Every major module must have tests.
4. Keep real and synthetic data clearly separated.
5. Keep baseline methods separate from the proposed mechanism.
6. Record important algorithmic decisions.
7. Do not claim novelty merely because an implementation works.
8. Do not use medical claims that are unsupported by the dataset.
9. The prototype is for research/engineering demonstration, not clinical use.
10. Every change to the core Twin State mechanism must be documented.

---

## 14. Open Questions

- [ ] Finalize public dataset.
- [ ] Finalize state variables.
- [ ] Finalize exact reliability calculation.
- [ ] Finalize mathematical formulation of the state update.
- [ ] Determine how uncertainty will be represented.
- [ ] Determine how synthetic longitudinal data will be generated.
- [ ] Determine progression target.
- [ ] Determine counterfactual propagation mechanism.
- [ ] Perform prior-art research.
- [ ] Evaluate whether the proposed mechanism provides measurable technical improvement.

---

## 15. Session Log

Append a short dated entry after every significant development session.

Example:

```text
2026-09-02:
Architecture revised. Reliability-aware Bayesian state updating selected as the initial mechanism under investigation. Exact formulation remains subject to experimentation and prior-art review.
```