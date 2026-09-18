"""
Synthetic longitudinal COPD dataset generator.

IMPORTANT: This dataset is 100% synthetic and generated for a course/ML
demonstration project only. It is NOT real patient data and must never be
described or published as representing real clinical outcomes. The
relationships below (smoking -> faster decline, activity -> slower decline,
etc.) are simplified, directionally-realistic approximations loosely
inspired by general COPD epidemiology (e.g. the Fletcher-Peto FEV1 decline
pattern), not validated clinical formulas.

Design goals:
  - One row per (patient, visit) -- a longitudinal record.
  - Enough real signal that a trained regressor (RF / XGBoost) can learn
    something genuine and be evaluated meaningfully (MAE/RMSE/R2).
  - Enough realistic messiness (missing values, occasional outliers,
    variable visit spacing) that a real preprocessing step has work to do.
  - A schema that supports "digital twin" mechanics directly:
      * baseline_* columns = static twin identity (set at Visit 1)
      * current_* / *_at_visit columns = time-varying twin state
      * months_since_baseline = the sweep variable for trajectory simulation
      * smoking_status_at_visit / activity_level_at_visit = the exact
        variables a "what-if" scenario changes (e.g. flip current smoker
        -> former smoker partway through the patient's timeline)
  - injected_issue column = ground truth for grading/demo purposes only.
    Do NOT feed this into model training -- it exists so you can show a
    "before cleaning vs after cleaning" comparison in your report.
"""

import numpy as np
import pandas as pd

RNG_SEED = 42
N_PATIENTS = 400
OUTPUT_PATH = "data/raw/copd_synthetic_longitudinal.csv"
DICT_PATH = "notes/data_dictionary.md"

rng = np.random.default_rng(RNG_SEED)

GOLD_STAGES = ["I (Mild)", "II (Moderate)", "III (Severe)", "IV (Very Severe)"]
GOLD_PROBS = [0.18, 0.40, 0.30, 0.12]
GOLD_FEV1_PCT_RANGE = {
    "I (Mild)": (80, 100),
    "II (Moderate)": (50, 79),
    "III (Severe)": (30, 49),
    "IV (Very Severe)": (15, 29),
}
GOLD_SEVERITY_MULT = {
    "I (Mild)": 0.90,
    "II (Moderate)": 1.00,
    "III (Severe)": 1.10,
    "IV (Very Severe)": 1.15,
}

SMOKING_STATUSES = ["never", "former", "current"]
SMOKING_PROBS = [0.15, 0.45, 0.40]
SMOKING_DECLINE_MULT = {"never": 1.00, "former": 1.30, "current": 1.80}

ACTIVITY_LEVELS = ["low", "moderate", "high"]
ACTIVITY_DECLINE_MULT = {"low": 1.15, "moderate": 1.00, "high": 0.85}


def sample_patient_baseline(pid):
    age = float(np.clip(rng.normal(63, 9), 40, 90))
    sex = rng.choice(["M", "F"], p=[0.55, 0.45])
    smoking_status = rng.choice(SMOKING_STATUSES, p=SMOKING_PROBS)
    pack_years = 0.0
    if smoking_status in ("former", "current"):
        pack_years = float(np.clip(rng.normal(32, 14), 2, 90))

    gold_stage = rng.choice(GOLD_STAGES, p=GOLD_PROBS)
    pct_lo, pct_hi = GOLD_FEV1_PCT_RANGE[gold_stage]
    fev1_pct_predicted = float(rng.uniform(pct_lo, pct_hi))

    # crude predicted-normal FEV1 (very rough, sex/age/height-free simplification)
    predicted_normal_fev1 = 3.9 if sex == "M" else 3.1
    predicted_normal_fev1 *= float(np.clip(1 - 0.008 * (age - 40), 0.6, 1.05))

    baseline_fev1 = predicted_normal_fev1 * (fev1_pct_predicted / 100.0)
    baseline_fev1 = float(np.clip(baseline_fev1, 0.5, 4.5))

    # obstruction ratio (FEV1/FVC) - lower = more severe obstruction
    baseline_ratio = float(np.clip(rng.normal(0.58, 0.08) - 0.03 * GOLD_STAGES.index(gold_stage), 0.30, 0.75))
    baseline_fvc = float(np.clip(baseline_fev1 / baseline_ratio, baseline_fev1 + 0.2, 6.0))

    activity_level = rng.choice(
        ACTIVITY_LEVELS,
        p=[0.5, 0.35, 0.15] if gold_stage in ("III (Severe)", "IV (Very Severe)") else [0.25, 0.45, 0.30],
    )
    bmi = float(np.clip(rng.normal(26, 5), 15, 45))

    # unobserved patient-specific frailty/heterogeneity multiplier on decline rate
    frailty_mult = float(np.clip(rng.normal(1.0, 0.20), 0.5, 1.8))

    # baseline annual FEV1 decline rate in liters/year (Fletcher-Peto-inspired baseline ~0.03L/yr for healthy agers)
    base_decline_L_per_year = 0.030
    decline_rate = (
        base_decline_L_per_year
        * SMOKING_DECLINE_MULT[smoking_status]
        * ACTIVITY_DECLINE_MULT[activity_level]
        * GOLD_SEVERITY_MULT[gold_stage]
        * (1 + 0.006 * max(0.0, age - 65))
        * frailty_mult
    )

    return {
        "patient_id": pid,
        "sex": sex,
        "age_at_baseline": round(age, 1),
        "gold_stage_baseline": gold_stage,
        "smoking_status_baseline": smoking_status,
        "pack_years": round(pack_years, 1),
        "baseline_fev1_liters": round(baseline_fev1, 3),
        "baseline_fvc_liters": round(baseline_fvc, 3),
        "baseline_fev1_fvc_ratio": round(baseline_ratio, 3),
        "baseline_activity_level": activity_level,
        "bmi": round(bmi, 1),
        "_decline_rate": decline_rate,
        "_frailty_mult": frailty_mult,
    }


def maybe_smoking_cessation_event(current_status, months_in):
    """Currently-smoking patients have a chance to quit at any given visit
    after month 6, simulating a real behavioral change the twin should react to."""
    if current_status == "current" and months_in > 6 and rng.random() < 0.06:
        return "former"
    return current_status


def maybe_activity_change(current_level, months_in):
    """Small chance of an activity-level change visit-to-visit (deconditioning
    or a deliberate lifestyle change)."""
    if rng.random() < 0.08:
        idx = ACTIVITY_LEVELS.index(current_level)
        idx = int(np.clip(idx + rng.choice([-1, 1]), 0, len(ACTIVITY_LEVELS) - 1))
        return ACTIVITY_LEVELS[idx]
    return current_level


def generate_patient_visits(baseline):
    rows = []
    n_visits = int(rng.integers(3, 9))  # 3-8 visits
    months = 0.0
    current_smoking = baseline["smoking_status_baseline"]
    current_activity = baseline["baseline_activity_level"]
    decline_rate = baseline["_decline_rate"]

    for visit_num in range(1, n_visits + 1):
        if visit_num > 1:
            gap = float(rng.uniform(3, 12))  # irregular visit spacing, 3-12 months
            months += gap
            current_smoking = maybe_smoking_cessation_event(current_smoking, months)
            current_activity = maybe_activity_change(current_activity, months)
            # cessation immediately drops the multiplier used going forward
            if current_smoking != baseline["smoking_status_baseline"]:
                decline_rate = (
                    decline_rate
                    / SMOKING_DECLINE_MULT[baseline["smoking_status_baseline"]]
                    * SMOKING_DECLINE_MULT[current_smoking]
                )

        years = months / 12.0
        measurement_noise = rng.normal(0, 0.05)
        fev1 = baseline["baseline_fev1_liters"] - decline_rate * years + measurement_noise

        # occasional acute exacerbation: temporary FEV1 dip + CAT bump
        exacerbation = 0
        exac_prob = 0.05 + 0.10 * (current_smoking == "current") + 0.08 * (
            baseline["gold_stage_baseline"] in ("III (Severe)", "IV (Very Severe)")
        )
        if rng.random() < exac_prob:
            exacerbation = int(rng.integers(1, 3))
            fev1 -= 0.05 * exacerbation

        fev1 = float(np.clip(fev1, 0.35, 4.5))

        ratio_drift = baseline["baseline_fev1_fvc_ratio"] - 0.01 * years + rng.normal(0, 0.01)
        ratio = float(np.clip(ratio_drift, 0.28, 0.80))
        fvc = float(np.clip(fev1 / ratio, fev1 + 0.15, 6.2))

        severity_index = 1 - (fev1 / baseline["baseline_fev1_liters"])
        spo2 = 97.5 - 6.0 * severity_index - 1.5 * exacerbation + rng.normal(0, 0.8)
        spo2 = float(np.clip(spo2, 82, 99))

        cat_score = 8 + 22 * severity_index + 3 * exacerbation + rng.normal(0, 2.0)
        cat_score = float(np.clip(cat_score, 0, 40))

        # Acute exacerbation in next 12 months (binary target: 0 or 1)
        # Probability increases with: low fev1_liters, high pack_years, smoking_status_at_visit == 'current', severe gold_stage_baseline
        gold_risk_map = {
            "I (Mild)": -0.60,
            "II (Moderate)": 0.00,
            "III (Severe)": 0.70,
            "IV (Very Severe)": 1.15,
        }
        gold_term = gold_risk_map.get(baseline["gold_stage_baseline"], 0.0)
        smoking_term = 1.30 if current_smoking == "current" else (0.15 if current_smoking == "former" else 0.0)
        pack_years_term = 0.020 * baseline["pack_years"]
        fev1_term = -1.15 * (fev1 - 2.0)  # Lower FEV1 increases logit

        logit_exac = -1.45 + gold_term + smoking_term + pack_years_term + fev1_term
        prob_exac = float(1.0 / (1.0 + np.exp(-np.clip(logit_exac, -5.0, 5.0))))
        prob_exac = float(np.clip(prob_exac, 0.05, 0.95))
        exacerbation_in_next_12m = int(rng.random() < prob_exac)

        rows.append(
            {
                "patient_id": baseline["patient_id"],
                "visit_number": visit_num,
                "months_since_baseline": round(months, 1),
                "sex": baseline["sex"],
                "age_at_visit": round(baseline["age_at_baseline"] + years, 1),
                "gold_stage_baseline": baseline["gold_stage_baseline"],
                "smoking_status_baseline": baseline["smoking_status_baseline"],
                "smoking_status_at_visit": current_smoking,
                "pack_years": baseline["pack_years"],
                "activity_level_at_visit": current_activity,
                "bmi": baseline["bmi"],
                "baseline_fev1_liters": baseline["baseline_fev1_liters"],
                "baseline_fvc_liters": baseline["baseline_fvc_liters"],
                "baseline_fev1_fvc_ratio": baseline["baseline_fev1_fvc_ratio"],
                "fev1_liters": round(fev1, 3),
                "fvc_liters": round(fvc, 3),
                "fev1_fvc_ratio": round(ratio, 3),
                "spo2_pct": round(spo2, 1),
                "cat_score": round(cat_score, 1),
                "exacerbations_this_visit": exacerbation,
                "exacerbation_in_next_12m": exacerbation_in_next_12m,
                "measurement_source": rng.choice(["clinic", "home_device"], p=[0.75, 0.25]),
                "injected_issue": "none",
            }
        )
    return rows


def inject_data_quality_issues(df):
    """Adds realistic missingness and a small number of outliers, with the
    ground truth recorded in injected_issue for grading/demo purposes only.
    Do not use injected_issue as a model input."""
    n = len(df)

    # ~4% missing SpO2 (device not used / reading skipped)
    miss_idx = rng.choice(n, size=int(0.04 * n), replace=False)
    df.loc[miss_idx, "spo2_pct"] = np.nan
    df.loc[miss_idx, "injected_issue"] = "missing_spo2"

    # ~3% missing CAT score (questionnaire not completed)
    remaining = df.index[df["injected_issue"] == "none"]
    miss_idx2 = rng.choice(remaining, size=int(0.03 * n), replace=False)
    df.loc[miss_idx2, "cat_score"] = np.nan
    df.loc[miss_idx2, "injected_issue"] = "missing_cat"

    # ~1.5% implausible outlier FEV1 (data entry / device error)
    remaining = df.index[df["injected_issue"] == "none"]
    out_idx = rng.choice(remaining, size=int(0.015 * n), replace=False)
    direction = rng.choice([-1, 1], size=len(out_idx))
    df.loc[out_idx, "fev1_liters"] = (
        df.loc[out_idx, "fev1_liters"] + direction * rng.uniform(1.2, 2.0, size=len(out_idx))
    ).clip(lower=0.1)
    df.loc[out_idx, "injected_issue"] = "outlier_fev1"

    return df


def main():
    all_rows = []
    for i in range(1, N_PATIENTS + 1):
        pid = f"P{i:04d}"
        baseline = sample_patient_baseline(pid)
        all_rows.extend(generate_patient_visits(baseline))

    df = pd.DataFrame(all_rows)
    df = inject_data_quality_issues(df)
    df = df.sort_values(["patient_id", "visit_number"]).reset_index(drop=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Patients: {df['patient_id'].nunique()}")
    print(f"Total rows: {len(df)}")
    print(f"Visits per patient: min={df.groupby('patient_id').size().min()}, "
          f"max={df.groupby('patient_id').size().max()}, "
          f"mean={df.groupby('patient_id').size().mean():.2f}")
    print(f"Missing spo2: {df['spo2_pct'].isna().sum()}")
    print(f"Missing cat_score: {df['cat_score'].isna().sum()}")
    print(f"Injected outliers: {(df['injected_issue'] == 'outlier_fev1').sum()}")
    print(f"Smoking cessation events present: "
          f"{(df['smoking_status_baseline'] != df['smoking_status_at_visit']).sum()} rows show a changed status")
    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
