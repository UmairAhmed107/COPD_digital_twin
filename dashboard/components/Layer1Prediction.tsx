"use client";

import React, { useState, useEffect } from "react";
import { Cpu, CheckCircle2, AlertCircle, ArrowRight, RefreshCw } from "lucide-react";
import { predictFEV1 } from "../lib/api";
import { PredictRequest, PredictResponse } from "../lib/types";
import { GoldenPatient } from "../lib/goldenPatients";

interface Layer1PredictionProps {
  initialValues?: PredictRequest;
  activeGoldenPatient?: GoldenPatient | null;
}

const DEFAULT_INPUTS: PredictRequest = {
  age_at_visit: 65.0,
  sex: "M",
  gold_stage_baseline: "II (Moderate)",
  smoking_status_at_visit: "former",
  pack_years: 35.0,
  activity_level_at_visit: "moderate",
  bmi: 26.2,
  months_since_baseline: 12.0,
  baseline_fev1_liters: 2.10,
};

export default function Layer1Prediction({
  initialValues,
  activeGoldenPatient,
}: Layer1PredictionProps) {
  const [formData, setFormData] = useState<PredictRequest>(initialValues || DEFAULT_INPUTS);
  const [modelType, setModelType] = useState<"random_forest" | "xgboost">("random_forest");
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sync when golden patient changes
  useEffect(() => {
    if (activeGoldenPatient) {
      setFormData(activeGoldenPatient.samplePredictValues);
    }
  }, [activeGoldenPatient]);

  const handleChange = (field: keyof PredictRequest, value: string | number) => {
    setFormData((prev) => ({
      ...prev,
      [field]: typeof prev[field] === "number" ? Number(value) : value,
    }));
  };

  const handlePredict = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const resp = await predictFEV1(formData, modelType);
      setResult(resp);
    } catch (err: any) {
      setError(err.message || "Failed to generate prediction.");
    } finally {
      setLoading(false);
    }
  };

  // Run initial prediction on load
  useEffect(() => {
    handlePredict();
  }, [modelType]);

  const fev1BaselineRatio =
    result && formData.baseline_fev1_liters > 0
      ? ((result.predicted_fev1_liters / formData.baseline_fev1_liters) * 100).toFixed(1)
      : null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "1.5rem" }}>
      {/* Left Column: Manual Form */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <Cpu size={19} color="#0d9488" />
              Layer 1: Single Prediction Form
            </h2>
            <p className="card-subtitle">
              Enter clinical characteristics to compute instant FEV1 lung function inference.
            </p>
          </div>

          <div style={{ display: "flex", gap: "0.25rem", background: "var(--bg-surface-secondary)", padding: "0.2rem", borderRadius: "var(--radius-md)" }}>
            <button
              id="model-rf-btn"
              type="button"
              className={`btn btn-secondary ${modelType === "random_forest" ? "active" : ""}`}
              style={{
                fontSize: "0.75rem",
                padding: "0.3rem 0.6rem",
                backgroundColor: modelType === "random_forest" ? "white" : "transparent",
                borderColor: modelType === "random_forest" ? "var(--border-light)" : "transparent",
                color: modelType === "random_forest" ? "var(--teal-primary)" : "var(--text-secondary)",
              }}
              onClick={() => setModelType("random_forest")}
            >
              Random Forest
            </button>
            <button
              id="model-xgb-btn"
              type="button"
              className={`btn btn-secondary ${modelType === "xgboost" ? "active" : ""}`}
              style={{
                fontSize: "0.75rem",
                padding: "0.3rem 0.6rem",
                backgroundColor: modelType === "xgboost" ? "white" : "transparent",
                borderColor: modelType === "xgboost" ? "var(--border-light)" : "transparent",
                color: modelType === "xgboost" ? "var(--teal-primary)" : "var(--text-secondary)",
              }}
              onClick={() => setModelType("xgboost")}
            >
              XGBoost
            </button>
          </div>
        </div>

        <form onSubmit={handlePredict} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="input-age" className="form-label">Age at Visit (years)</label>
              <input
                id="input-age"
                type="number"
                step="0.5"
                min="40"
                max="90"
                className="form-input"
                value={formData.age_at_visit}
                onChange={(e) => handleChange("age_at_visit", e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="input-sex" className="form-label">Biological Sex</label>
              <select
                id="input-sex"
                className="form-select"
                value={formData.sex}
                onChange={(e) => handleChange("sex", e.target.value)}
              >
                <option value="M">Male (M)</option>
                <option value="F">Female (F)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="input-gold" className="form-label">Baseline GOLD Stage</label>
              <select
                id="input-gold"
                className="form-select"
                value={formData.gold_stage_baseline}
                onChange={(e) => handleChange("gold_stage_baseline", e.target.value)}
              >
                <option value="I (Mild)">Stage I (Mild)</option>
                <option value="II (Moderate)">Stage II (Moderate)</option>
                <option value="III (Severe)">Stage III (Severe)</option>
                <option value="IV (Very Severe)">Stage IV (Very Severe)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="input-smoking" className="form-label">Smoking Status at Visit</label>
              <select
                id="input-smoking"
                className="form-select"
                value={formData.smoking_status_at_visit}
                onChange={(e) => handleChange("smoking_status_at_visit", e.target.value)}
              >
                <option value="never">Never Smoker</option>
                <option value="former">Former Smoker</option>
                <option value="current">Current Smoker</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="input-pack-years" className="form-label">Cumulative Pack-Years</label>
              <input
                id="input-pack-years"
                type="number"
                step="0.5"
                min="0"
                max="120"
                className="form-input"
                value={formData.pack_years}
                onChange={(e) => handleChange("pack_years", e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="input-activity" className="form-label">Physical Activity Level</label>
              <select
                id="input-activity"
                className="form-select"
                value={formData.activity_level_at_visit}
                onChange={(e) => handleChange("activity_level_at_visit", e.target.value)}
              >
                <option value="low">Low (Sedentary)</option>
                <option value="moderate">Moderate</option>
                <option value="high">High (Active)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="input-bmi" className="form-label">Body Mass Index (BMI)</label>
              <input
                id="input-bmi"
                type="number"
                step="0.1"
                min="14"
                max="50"
                className="form-input"
                value={formData.bmi}
                onChange={(e) => handleChange("bmi", e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="input-months" className="form-label">Months Since Baseline</label>
              <input
                id="input-months"
                type="number"
                step="1"
                min="0"
                max="120"
                className="form-input"
                value={formData.months_since_baseline}
                onChange={(e) => handleChange("months_since_baseline", e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="input-baseline-fev1" className="form-label">Baseline FEV1 (Liters)</label>
              <input
                id="input-baseline-fev1"
                type="number"
                step="0.01"
                min="0.4"
                max="5.5"
                className="form-input"
                value={formData.baseline_fev1_liters}
                onChange={(e) => handleChange("baseline_fev1_liters", e.target.value)}
                required
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
            <button
              id="predict-submit-btn"
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ flex: 1 }}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  Running Inference...
                </>
              ) : (
                <>
                  <ArrowRight size={16} />
                  Compute Prediction ({modelType === "xgboost" ? "XGBoost" : "Random Forest"})
                </>
              )}
            </button>
            <button
              id="predict-reset-btn"
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setFormData(DEFAULT_INPUTS);
                setResult(null);
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {/* Right Column: Prediction Output Card */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {error && (
          <div className="alert-box alert-error">
            <AlertCircle size={18} />
            <div>
              <strong>Inference Error:</strong> {error}
            </div>
          </div>
        )}

        <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="card-header">
              <div>
                <h3 className="card-title">Predicted Lung Function</h3>
                <p className="card-subtitle">Immediate spirometric volume estimate</p>
              </div>
              {result && (
                <span className="badge badge-demo" style={{ textTransform: "capitalize" }}>
                  Model: {result.model_used.replace("_", " ")}
                </span>
              )}
            </div>

            {result ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div className="metric-highlight-card">
                  <span className="metric-label-large">Projected FEV1 Volume</span>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                    <span className="metric-value-large">{result.predicted_fev1_liters.toFixed(3)}</span>
                    <span style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-secondary)" }}>Liters</span>
                  </div>
                  {fev1BaselineRatio && (
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                      <strong>{fev1BaselineRatio}%</strong> of baseline lung volume ({formData.baseline_fev1_liters} L)
                    </span>
                  )}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div style={{ padding: "0.75rem", borderRadius: "var(--radius-md)", background: "var(--bg-surface-secondary)" }}>
                    <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                      Observed Drop
                    </div>
                    <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      {(formData.baseline_fev1_liters - result.predicted_fev1_liters).toFixed(3)} L
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      over {formData.months_since_baseline} months
                    </div>
                  </div>

                  <div style={{ padding: "0.75rem", borderRadius: "var(--radius-md)", background: "var(--bg-surface-secondary)" }}>
                    <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                      Annualized Decline
                    </div>
                    <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      {formData.months_since_baseline > 0
                        ? `${(((formData.baseline_fev1_liters - result.predicted_fev1_liters) / (formData.months_since_baseline / 12)) * 1000).toFixed(0)} mL/yr`
                        : "Baseline visit"}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      expected COPD loss rate
                    </div>
                  </div>
                </div>

                <div style={{ padding: "0.75rem 1rem", borderLeft: "3px solid var(--teal-primary)", background: "var(--teal-light)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--teal-primary)", marginBottom: "0.2rem" }}>
                    Clinical Insight
                  </div>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                    Model features isolate non-leaking drivers. Downstream consequence metrics (such as SpO2 and CAT symptom scores) were strictly omitted from the model matrix to ensure authentic predictive validity.
                  </p>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
                Fill out the form and submit to view the predicted lung capacity.
              </div>
            )}
          </div>

          <div style={{ borderTop: "1px solid var(--border-light)", paddingTop: "0.75rem", marginTop: "1rem", display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-muted)" }}>
            <span>9 approved inputs strictly enforced</span>
            <span style={{ display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--emerald-primary)" }}>
              <CheckCircle2 size={13} /> Zero leakage compliant
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
