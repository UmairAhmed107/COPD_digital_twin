"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Cpu,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  RefreshCw,
  Activity,
  Zap,
  Sliders,
  Sparkles,
  ShieldAlert,
} from "lucide-react";
import { predictFEV1 } from "../lib/api";
import { PredictRequest, PredictResponse } from "../lib/types";
import { GoldenPatient } from "../lib/goldenPatients";
import { useToast } from "../context/ToastContext";

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

function getBMICategory(bmi: number): { label: string; color: string } {
  if (bmi < 18.5) return { label: "Underweight", color: "var(--amber-primary)" };
  if (bmi < 25.0) return { label: "Normal Weight", color: "var(--emerald-primary)" };
  if (bmi < 30.0) return { label: "Overweight", color: "var(--amber-primary)" };
  return { label: "Obese (Class I+)", color: "var(--rose-primary)" };
}

export default function Layer1Prediction({
  initialValues,
  activeGoldenPatient,
}: Layer1PredictionProps) {
  const { showToast } = useToast();
  const [formData, setFormData] = useState<PredictRequest>(initialValues || DEFAULT_INPUTS);
  const [modelType, setModelType] = useState<"random_forest" | "xgboost">("random_forest");
  const [loading, setLoading] = useState<boolean>(false);
  const [isDebouncing, setIsDebouncing] = useState<boolean>(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isFirstMount = useRef(true);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastAlertTriggerRef = useRef<string>("");

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

  const handlePredict = useCallback(
    async (overrideData?: PredictRequest) => {
      const dataToPredict = overrideData || formData;
      setLoading(true);
      setError(null);

      try {
        const resp = await predictFEV1(dataToPredict, modelType);
        setResult(resp);

        // Threshold Alert Evaluation: Exacerbation Risk > 60% or GOLD IV (FEV1 <= 0.90L)
        const risk = resp.exacerbation_risk_pct ?? 0;
        const fev1 = resp.predicted_fev1_liters;

        if (risk >= 60.0 && lastAlertTriggerRef.current !== "high_risk") {
          lastAlertTriggerRef.current = "high_risk";
          showToast({
            type: "critical",
            title: "⚠️ High Risk of Acute Exacerbation",
            message: `Projected 12-month exacerbation likelihood has reached ${risk.toFixed(1)}%. Immediate clinical risk mitigation advised.`,
          });
        } else if (fev1 <= 0.90 && lastAlertTriggerRef.current !== "gold_iv") {
          lastAlertTriggerRef.current = "gold_iv";
          showToast({
            type: "critical",
            title: "⚠️ Critical Threshold: GOLD Stage IV",
            message: `Projected FEV1 is ${fev1.toFixed(3)}L (<=0.90L), indicating very severe airflow limitation.`,
          });
        } else if (risk < 50.0 && fev1 > 1.0) {
          // Reset alert latch when patient parameters return to safer range
          lastAlertTriggerRef.current = "";
        }
      } catch (err: any) {
        setError(err.message || "Failed to generate prediction.");
      } finally {
        setLoading(false);
      }
    },
    [formData, modelType, showToast]
  );

  // 300ms Debounce: automatically calls API as user adjusts any slider/input
  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      handlePredict();
      return;
    }

    setIsDebouncing(true);
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      setIsDebouncing(false);
      handlePredict();
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [formData, modelType, handlePredict]);

  // Activity level slider indexing: 0 = low, 1 = moderate, 2 = high
  const activityLevelIndex =
    formData.activity_level_at_visit === "high"
      ? 2
      : formData.activity_level_at_visit === "low"
      ? 0
      : 1;

  const handleActivitySliderChange = (idx: number) => {
    const map = ["low", "moderate", "high"];
    handleChange("activity_level_at_visit", map[idx] || "moderate");
  };

  const fev1BaselineRatio =
    result && formData.baseline_fev1_liters > 0
      ? ((result.predicted_fev1_liters / formData.baseline_fev1_liters) * 100).toFixed(1)
      : null;

  // Real-time Composite Health Score calculation (0 - 100)
  const fev1Norm = result
    ? Math.min(100, Math.max(0, (result.predicted_fev1_liters / 3.0) * 100))
    : 0;
  const riskNorm = result ? Math.max(0, 100 - (result.exacerbation_risk_pct || 0)) : 0;
  const liveHealthScore = result ? Math.round(0.6 * fev1Norm + 0.4 * riskNorm) : null;

  let healthScoreColor = "var(--emerald-primary)";
  let healthScoreBg = "var(--emerald-light)";
  let healthScoreBorder = "var(--emerald-border)";
  let healthScoreLabel = "Optimal / Compensated";

  if (liveHealthScore !== null) {
    if (liveHealthScore < 50) {
      healthScoreColor = "var(--rose-primary)";
      healthScoreBg = "var(--rose-light)";
      healthScoreBorder = "var(--rose-border)";
      healthScoreLabel = "Critical / Severe Risk";
    } else if (liveHealthScore < 75) {
      healthScoreColor = "var(--amber-primary)";
      healthScoreBg = "var(--amber-light)";
      healthScoreBorder = "var(--amber-border)";
      healthScoreLabel = "Guarded / Moderate Obstruction";
    }
  }

  const bmiMeta = getBMICategory(formData.bmi);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "1.5rem" }}>
      {/* Left Column: Live Slider Playground */}
      <div className="card">
        <div className="card-header">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h2 className="card-title">
                <Cpu size={19} color="#0d9488" />
                Layer 1: Live Slider Playground
              </h2>
              {isDebouncing ? (
                <span
                  className="badge"
                  style={{
                    background: "var(--teal-light)",
                    borderColor: "var(--teal-border)",
                    color: "var(--teal-primary)",
                    fontSize: "0.7rem",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem",
                  }}
                >
                  <RefreshCw size={11} className="animate-spin" />
                  Auto-calibrating...
                </span>
              ) : (
                <span
                  className="badge"
                  style={{
                    background: "var(--bg-surface-secondary)",
                    color: "var(--text-muted)",
                    fontSize: "0.7rem",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.25rem",
                  }}
                >
                  <Zap size={11} color="var(--amber-primary)" />
                  300ms Live Debounced
                </span>
              )}
            </div>
            <p className="card-subtitle">
              Drag interactive sliders to immediately recompute FEV1 volume and composite health score.
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

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handlePredict();
          }}
          style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
        >
          {/* Section 1: Tactile Range Sliders Highlight */}
          <div
            style={{
              padding: "1rem",
              background: "linear-gradient(135deg, #f8fafc, #f1f5f9)",
              border: "1px solid var(--border-light)",
              borderRadius: "var(--radius-md)",
              display: "flex",
              flexDirection: "column",
              gap: "1.25rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.75rem", fontWeight: 700, color: "var(--teal-primary)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
              <Sliders size={14} />
              Tactile Clinical Sliders (Live Updates)
            </div>

            {/* Slider 1: Cumulative Pack-Years */}
            <div className="form-group" style={{ margin: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                <label htmlFor="input-pack-years" className="form-label" style={{ margin: 0 }}>
                  Cumulative Pack-Years
                </label>
                <span
                  className="badge"
                  style={{
                    background: formData.pack_years >= 50 ? "var(--rose-light)" : formData.pack_years >= 25 ? "var(--amber-light)" : "var(--teal-light)",
                    color: formData.pack_years >= 50 ? "var(--rose-primary)" : formData.pack_years >= 25 ? "var(--amber-primary)" : "var(--teal-primary)",
                    borderColor: formData.pack_years >= 50 ? "var(--rose-border)" : formData.pack_years >= 25 ? "var(--amber-border)" : "var(--teal-border)",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                  }}
                >
                  {formData.pack_years} pack-years
                </span>
              </div>
              <input
                id="input-pack-years"
                type="range"
                min="0"
                max="100"
                step="1"
                className="form-range"
                value={formData.pack_years}
                onChange={(e) => handleChange("pack_years", e.target.value)}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                <span>0 (Non-smoker)</span>
                <span>25</span>
                <span>50</span>
                <span>75</span>
                <span>100+</span>
              </div>
            </div>

            {/* Slider 2: BMI */}
            <div className="form-group" style={{ margin: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                <label htmlFor="input-bmi" className="form-label" style={{ margin: 0 }}>
                  Body Mass Index (BMI)
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                  <span
                    className="badge"
                    style={{
                      background: bmiMeta.color === "var(--emerald-primary)" ? "var(--emerald-light)" : bmiMeta.color === "var(--rose-primary)" ? "var(--rose-light)" : "var(--amber-light)",
                      color: bmiMeta.color,
                      fontSize: "0.75rem",
                      fontWeight: 700,
                    }}
                  >
                    BMI {Number(formData.bmi).toFixed(1)} &bull; {bmiMeta.label}
                  </span>
                </div>
              </div>
              <input
                id="input-bmi"
                type="range"
                min="15"
                max="45"
                step="0.1"
                className="form-range"
                value={formData.bmi}
                onChange={(e) => handleChange("bmi", e.target.value)}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                <span>15 (Underweight)</span>
                <span>25 (Normal)</span>
                <span>30 (Overweight)</span>
                <span>45 (Obese)</span>
              </div>
            </div>

            {/* Slider 3: Physical Activity Level (Discrete 3-Step Slider) */}
            <div className="form-group" style={{ margin: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                <label htmlFor="input-activity-slider" className="form-label" style={{ margin: 0 }}>
                  Physical Activity Level
                </label>
                <span
                  className="badge"
                  style={{
                    background:
                      formData.activity_level_at_visit === "high"
                        ? "var(--emerald-light)"
                        : formData.activity_level_at_visit === "low"
                        ? "var(--rose-light)"
                        : "var(--blue-light)",
                    color:
                      formData.activity_level_at_visit === "high"
                        ? "var(--emerald-primary)"
                        : formData.activity_level_at_visit === "low"
                        ? "var(--rose-primary)"
                        : "var(--blue-primary)",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "capitalize",
                  }}
                >
                  {formData.activity_level_at_visit} Intensity
                </span>
              </div>
              <input
                id="input-activity-slider"
                type="range"
                min="0"
                max="2"
                step="1"
                className="form-range"
                value={activityLevelIndex}
                onChange={(e) => handleActivitySliderChange(Number(e.target.value))}
              />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", textAlign: "center", marginTop: "0.35rem", gap: "0.25rem" }}>
                <button
                  type="button"
                  style={{
                    cursor: "pointer",
                    background: activityLevelIndex === 0 ? "var(--rose-light)" : "transparent",
                    color: activityLevelIndex === 0 ? "var(--rose-primary)" : "var(--text-muted)",
                    border: `1px solid ${activityLevelIndex === 0 ? "var(--rose-border)" : "transparent"}`,
                    borderRadius: "var(--radius-sm)",
                    padding: "0.2rem 0.35rem",
                    fontSize: "0.6875rem",
                    fontWeight: activityLevelIndex === 0 ? 700 : 500,
                  }}
                  onClick={() => handleActivitySliderChange(0)}
                >
                  Low (Sedentary)
                </button>
                <button
                  type="button"
                  style={{
                    cursor: "pointer",
                    background: activityLevelIndex === 1 ? "var(--blue-light)" : "transparent",
                    color: activityLevelIndex === 1 ? "var(--blue-primary)" : "var(--text-muted)",
                    border: `1px solid ${activityLevelIndex === 1 ? "var(--blue-border)" : "transparent"}`,
                    borderRadius: "var(--radius-sm)",
                    padding: "0.2rem 0.35rem",
                    fontSize: "0.6875rem",
                    fontWeight: activityLevelIndex === 1 ? 700 : 500,
                  }}
                  onClick={() => handleActivitySliderChange(1)}
                >
                  Moderate
                </button>
                <button
                  type="button"
                  style={{
                    cursor: "pointer",
                    background: activityLevelIndex === 2 ? "var(--emerald-light)" : "transparent",
                    color: activityLevelIndex === 2 ? "var(--emerald-primary)" : "var(--text-muted)",
                    border: `1px solid ${activityLevelIndex === 2 ? "var(--emerald-border)" : "transparent"}`,
                    borderRadius: "var(--radius-sm)",
                    padding: "0.2rem 0.35rem",
                    fontSize: "0.6875rem",
                    fontWeight: activityLevelIndex === 2 ? 700 : 500,
                  }}
                  onClick={() => handleActivitySliderChange(2)}
                >
                  High (Active)
                </button>
              </div>
            </div>
          </div>

          {/* Section 2: Other Clinical Parameters Grid */}
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

          <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.25rem" }}>
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
                  Immediate Prediction ({modelType === "xgboost" ? "XGBoost" : "Random Forest"})
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
                lastAlertTriggerRef.current = "";
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {/* Right Column: Instant Prediction Output & Live Twin Health Score */}
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
                <h3 className="card-title">Instant Spirometric Prediction</h3>
                <p className="card-subtitle">Real-time inference driven by live tactile sliders</p>
              </div>
              {result && (
                <span className="badge badge-demo" style={{ textTransform: "capitalize" }}>
                  Model: {result.model_used.replace("_", " ")}
                </span>
              )}
            </div>

            {result ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {/* Primary Metric 1: Projected FEV1 */}
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

                {/* Primary Metric 2: Live Composite Twin Health Score */}
                {liveHealthScore !== null && (
                  <div
                    style={{
                      padding: "1rem 1.25rem",
                      background: healthScoreBg,
                      border: `1px solid ${healthScoreBorder}`,
                      borderRadius: "var(--radius-md)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "1rem",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: healthScoreColor, textTransform: "uppercase", letterSpacing: "0.03em" }}>
                        Live Composite Twin Health Score
                      </div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: "0.4rem", marginTop: "0.2rem" }}>
                        <span style={{ fontSize: "2rem", fontWeight: 800, color: healthScoreColor, letterSpacing: "-0.02em" }}>
                          {liveHealthScore}
                        </span>
                        <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)", fontWeight: 600 }}>/ 100</span>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: healthScoreColor, fontWeight: 700, marginTop: "0.15rem" }}>
                        {healthScoreLabel}
                      </div>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                        12-Mo Exacerbation Risk
                      </div>
                      <div style={{ fontSize: "1.35rem", fontWeight: 800, color: (result.exacerbation_risk_pct || 0) >= 50 ? "var(--rose-primary)" : "var(--teal-primary)", marginTop: "0.1rem" }}>
                        {(result.exacerbation_risk_pct || 0).toFixed(1)}%
                      </div>
                      <span
                        className="badge"
                        style={{
                          background: (result.exacerbation_risk_pct || 0) >= 60 ? "var(--rose-primary)" : "var(--bg-surface)",
                          color: (result.exacerbation_risk_pct || 0) >= 60 ? "#ffffff" : "var(--text-secondary)",
                          fontSize: "0.65rem",
                          fontWeight: 700,
                        }}
                      >
                        {(result.exacerbation_risk_pct || 0) >= 60 ? "Critical Tier" : "Monitored Tier"}
                      </span>
                    </div>
                  </div>
                )}

                {/* Sub-metrics Grid: Observed Drop & Decline Velocity */}
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
                Adjust the sliders or submit to compute live spirometric inference.
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
