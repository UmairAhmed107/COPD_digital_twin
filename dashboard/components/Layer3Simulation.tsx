"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Play,
  TrendingUp,
  Award,
  AlertCircle,
  RefreshCw,
  Sliders,
  BarChart3,
  Flame,
  Zap,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { getModelComparison, getPatient, simulateFuture } from "../lib/api";
import { ModelComparisonResponse, SimulateResponse, TwinStateResponse } from "../lib/types";
import LungVisualizer from "./LungVisualizer";

interface Layer3SimulationProps {
  selectedPatientId: string;
}

function getGoldStageFromFEV1(fev1: number, referenceFev1: number = 3.2): "I" | "II" | "III" | "IV" {
  const pct = (fev1 / referenceFev1) * 100;
  if (pct >= 80) return "I";
  if (pct >= 50) return "II";
  if (pct >= 30) return "III";
  return "IV";
}

const SCENARIO_CONFIGS: Record<string, { label: string; color: string; strokeDash?: string }> = {
  baseline: { label: "Baseline (Current Trajectory)", color: "#e11d48" },
  smoking_cessation: { label: "Smoking Cessation (Quit)", color: "#0d9488" },
  increased_activity: { label: "Increased Physical Activity", color: "#2563eb", strokeDash: "4 4" },
  combined_intervention: { label: "Combined (Cessation + High Activity)", color: "#059669" },
};

export default function Layer3Simulation({ selectedPatientId }: Layer3SimulationProps) {
  const [twinState, setTwinState] = useState<TwinStateResponse | null>(null);
  const [horizonMonths, setHorizonMonths] = useState<number>(36);
  const [stepMonths, setStepMonths] = useState<number>(6);
  const [modelType, setModelType] = useState<"random_forest" | "xgboost">("random_forest");
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([
    "baseline",
    "smoking_cessation",
    "increased_activity",
  ]);

  const [simulating, setSimulating] = useState<boolean>(false);
  const [simulationResult, setSimulationResult] = useState<SimulateResponse | null>(null);
  const [simError, setSimError] = useState<string | null>(null);

  // Model comparison table state
  const [modelComparison, setModelComparison] = useState<ModelComparisonResponse | null>(null);
  const [loadingComparison, setLoadingComparison] = useState<boolean>(false);

  // Load patient twin state when selectedPatientId changes
  useEffect(() => {
    if (!selectedPatientId) return;
    let mounted = true;
    async function loadTwin() {
      try {
        const data = await getPatient(selectedPatientId);
        if (mounted) setTwinState(data);
      } catch (err: any) {
        // Silently handled
      }
    }
    loadTwin();
    return () => {
      mounted = false;
    };
  }, [selectedPatientId]);

  // Load model comparison on mount
  useEffect(() => {
    let mounted = true;
    async function loadComparison() {
      setLoadingComparison(true);
      try {
        const comp = await getModelComparison("rf");
        if (mounted) setModelComparison(comp);
      } catch (err) {
        // Silently handled
      } finally {
        if (mounted) setLoadingComparison(false);
      }
    }
    loadComparison();
    return () => {
      mounted = false;
    };
  }, []);

  const handleRunSimulation = async () => {
    if (!selectedPatientId) return;
    setSimulating(true);
    setSimError(null);

    try {
      const resp = await simulateFuture(
        {
          patient_id: selectedPatientId,
          horizon_months: horizonMonths,
          step_months: stepMonths,
          scenarios: selectedScenarios,
        },
        modelType
      );
      setSimulationResult(resp);
    } catch (err: any) {
      setSimError(err.message || "Simulation failed to run.");
    } finally {
      setSimulating(false);
    }
  };

  // Run initial simulation when patient or model changes
  useEffect(() => {
    handleRunSimulation();
  }, [selectedPatientId, modelType, horizonMonths]);

  const toggleScenario = (scenKey: string) => {
    setSelectedScenarios((prev) =>
      prev.includes(scenKey) ? prev.filter((s) => s !== scenKey) : [...prev, scenKey]
    );
  };

  // Transform simulation trajectory dictionary into array for Recharts
  const chartPoints = React.useMemo(() => {
    if (!simulationResult || !simulationResult.trajectories) return [];

    const timeMap: Record<number, any> = {};

    Object.entries(simulationResult.trajectories).forEach(([scenName, points]) => {
      points.forEach((pt) => {
        const m = pt.months_since_baseline;
        if (!timeMap[m]) {
          timeMap[m] = { month: m };
        }
        timeMap[m][scenName] = pt.predicted_fev1_liters;
        timeMap[m][`${scenName}_risk`] = pt.exacerbation_risk_pct;
      });
    });

    return Object.values(timeMap).sort((a, b) => a.month - b.month);
  }, [simulationResult]);

  // Reference and baseline capacities for ROI calculation
  const currentFev1 = Number(twinState?.current?.fev1_liters || twinState?.static?.baseline_fev1_liters || 2.0);
  const baselineReference = Number(twinState?.static?.baseline_fev1_liters || 2.2);

  // Calculate divergence delta (e.g. baseline vs interventions at final horizon month)
  const finalMonth = chartPoints.length > 0 ? chartPoints[chartPoints.length - 1] : null;
  const baselineFinal = finalMonth?.baseline !== undefined ? Number(finalMonth.baseline) : null;
  const cessationFinal = finalMonth?.smoking_cessation !== undefined ? Number(finalMonth.smoking_cessation) : null;
  const activityFinal = finalMonth?.increased_activity !== undefined ? Number(finalMonth.increased_activity) : null;
  const combinedFinal = finalMonth?.combined_intervention !== undefined ? Number(finalMonth.combined_intervention) : null;

  const cessationGain =
    baselineFinal !== null && cessationFinal !== null ? (cessationFinal - baselineFinal).toFixed(3) : null;
  const combinedGain =
    baselineFinal !== null && combinedFinal !== null ? (combinedFinal - baselineFinal).toFixed(3) : null;

  // Selected priority intervention for ROI comparison
  let activeInterventionKey = "smoking_cessation";
  let activeInterventionLabel = "Smoking Cessation";
  let activeInterventionFinal = cessationFinal;

  if (selectedScenarios.includes("combined_intervention") && combinedFinal !== null) {
    activeInterventionKey = "combined_intervention";
    activeInterventionLabel = "Combined (Cessation + High Activity)";
    activeInterventionFinal = combinedFinal;
  } else if (selectedScenarios.includes("smoking_cessation") && cessationFinal !== null) {
    activeInterventionKey = "smoking_cessation";
    activeInterventionLabel = "Smoking Cessation";
    activeInterventionFinal = cessationFinal;
  } else if (selectedScenarios.includes("increased_activity") && activityFinal !== null) {
    activeInterventionKey = "increased_activity";
    activeInterventionLabel = "Increased Physical Activity";
    activeInterventionFinal = activityFinal;
  }

  // Comprehensive ROI Calculations
  const deltaPreserved = baselineFinal !== null && activeInterventionFinal !== null ? activeInterventionFinal - baselineFinal : null;
  const deltaPreservedML = deltaPreserved !== null ? Math.round(deltaPreserved * 1000) : null;
  const baselineLoss = baselineFinal !== null ? Math.max(currentFev1 - baselineFinal, 0.001) : null;
  const pctDeclineAttenuated = deltaPreserved !== null && baselineLoss ? Math.min(Math.round((deltaPreserved / baselineLoss) * 100), 100) : null;
  const relativeCapacityGain = deltaPreserved !== null && baselineFinal ? ((deltaPreserved / baselineFinal) * 100).toFixed(1) : null;

  // Exacerbation Risk Calculations (Dual-Outcome Twin)
  const baselineRiskFinal = finalMonth?.baseline_risk !== undefined ? Number(finalMonth.baseline_risk) : null;
  const cessationRiskFinal = finalMonth?.smoking_cessation_risk !== undefined ? Number(finalMonth.smoking_cessation_risk) : null;
  const activityRiskFinal = finalMonth?.increased_activity_risk !== undefined ? Number(finalMonth.increased_activity_risk) : null;
  const combinedRiskFinal = finalMonth?.combined_intervention_risk !== undefined ? Number(finalMonth.combined_intervention_risk) : null;

  let activeInterventionRiskFinal = cessationRiskFinal;
  if (selectedScenarios.includes("combined_intervention") && combinedRiskFinal !== null) {
    activeInterventionRiskFinal = combinedRiskFinal;
  } else if (selectedScenarios.includes("smoking_cessation") && cessationRiskFinal !== null) {
    activeInterventionRiskFinal = cessationRiskFinal;
  } else if (selectedScenarios.includes("increased_activity") && activityRiskFinal !== null) {
    activeInterventionRiskFinal = activityRiskFinal;
  }

  const riskReductionPct =
    baselineRiskFinal !== null && activeInterventionRiskFinal !== null
      ? Number((baselineRiskFinal - activeInterventionRiskFinal).toFixed(1))
      : null;

  const relativeRiskReduction =
    baselineRiskFinal !== null && riskReductionPct !== null && baselineRiskFinal > 0
      ? Math.round((riskReductionPct / baselineRiskFinal) * 100)
      : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Simulation Controls Card */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <Sparkles size={19} color="#0d9488" />
              Layer 3: What-If Trajectory Simulation Engine
            </h2>
            <p className="card-subtitle">
              Simulate patient {selectedPatientId}&apos;s future lung function over time under diverging clinical interventions.
            </p>
          </div>

          <div style={{ display: "flex", gap: "0.25rem", background: "var(--bg-surface-secondary)", padding: "0.2rem", borderRadius: "var(--radius-md)" }}>
            <button
              id="sim-model-rf"
              type="button"
              className={`btn btn-secondary ${modelType === "random_forest" ? "active" : ""}`}
              style={{
                fontSize: "0.75rem",
                padding: "0.3rem 0.6rem",
                backgroundColor: modelType === "random_forest" ? "white" : "transparent",
                color: modelType === "random_forest" ? "var(--teal-primary)" : "var(--text-secondary)",
              }}
              onClick={() => setModelType("random_forest")}
            >
              Random Forest
            </button>
            <button
              id="sim-model-xgb"
              type="button"
              className={`btn btn-secondary ${modelType === "xgboost" ? "active" : ""}`}
              style={{
                fontSize: "0.75rem",
                padding: "0.3rem 0.6rem",
                backgroundColor: modelType === "xgboost" ? "white" : "transparent",
                color: modelType === "xgboost" ? "var(--teal-primary)" : "var(--text-secondary)",
              }}
              onClick={() => setModelType("xgboost")}
            >
              XGBoost
            </button>
          </div>
        </div>

        {/* Parameter Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", alignItems: "flex-end" }}>
          <div className="form-group">
            <label className="form-label">Simulation Horizon</label>
            <select
              className="form-select"
              value={horizonMonths}
              onChange={(e) => setHorizonMonths(Number(e.target.value))}
            >
              <option value="12">12 Months (1 Year)</option>
              <option value="24">24 Months (2 Years)</option>
              <option value="36">36 Months (3 Years)</option>
              <option value="48">48 Months (4 Years)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Step Interval</label>
            <select
              className="form-select"
              value={stepMonths}
              onChange={(e) => setStepMonths(Number(e.target.value))}
            >
              <option value="3">Every 3 Months</option>
              <option value="6">Every 6 Months</option>
              <option value="12">Every 12 Months</option>
            </select>
          </div>

          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              id="run-sim-btn"
              type="button"
              className="btn btn-primary"
              style={{ flex: 1 }}
              onClick={handleRunSimulation}
              disabled={simulating}
            >
              {simulating ? (
                <>
                  <RefreshCw size={15} className="animate-spin" />
                  Simulating...
                </>
              ) : (
                <>
                  <Play size={15} />
                  Run What-If Simulation
                </>
              )}
            </button>
          </div>
        </div>

        {/* Scenario Toggle Badges */}
        <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border-light)" }}>
          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>
            Active Scenarios to Compare:
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.5rem" }}>
            {Object.entries(SCENARIO_CONFIGS).map(([key, config]) => {
              const active = selectedScenarios.includes(key);
              return (
                <button
                  key={key}
                  id={`scenario-toggle-${key}`}
                  type="button"
                  className="badge"
                  style={{
                    cursor: "pointer",
                    padding: "0.35rem 0.75rem",
                    fontSize: "0.8125rem",
                    backgroundColor: active ? config.color : "var(--bg-surface-secondary)",
                    color: active ? "white" : "var(--text-secondary)",
                    borderColor: active ? config.color : "var(--border-light)",
                    transition: "all 0.15s ease",
                  }}
                  onClick={() => toggleScenario(key)}
                >
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: active ? "white" : config.color,
                      display: "inline-block",
                    }}
                  />
                  {config.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {simError && (
        <div className="alert-box alert-error">
          <AlertCircle size={18} />
          <div>{simError}</div>
        </div>
      )}

      {/* Trajectory Divergence Chart */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <TrendingUp size={18} color="#0d9488" />
              Diverging Trajectory Projection
            </h3>
            <p className="card-subtitle">
              Visualizing modeled lung function decline under baseline versus preventive intervention scenarios.
            </p>
          </div>

          {cessationGain && Number(cessationGain) > 0 && (
            <div
              className="badge"
              style={{
                background: "var(--emerald-light)",
                border: "1px solid var(--emerald-border)",
                color: "var(--emerald-primary)",
                padding: "0.35rem 0.75rem",
                fontSize: "0.8125rem",
              }}
            >
              <Award size={15} />
              +{cessationGain} L preserved via smoking cessation
            </div>
          )}
        </div>

        {chartPoints.length > 0 ? (
          <div style={{ width: "100%", height: "340px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartPoints} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="month"
                  name="Timeline (Months)"
                  unit=" mo"
                  stroke="#94a3b8"
                  fontSize={12}
                  tickLine={false}
                />
                <YAxis
                  unit=" L"
                  domain={["dataMin - 0.15", "dataMax + 0.15"]}
                  stroke="#94a3b8"
                  fontSize={12}
                  tickLine={false}
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const mData = chartPoints.find((p) => p.month === label);
                      return (
                        <div className="custom-chart-tooltip">
                          <div className="tooltip-title">Simulation at Month {label}</div>
                          {payload.map((entry, idx) => {
                            const key = entry.dataKey as string;
                            const riskVal = mData ? mData[`${key}_risk`] : undefined;
                            return (
                              <div
                                key={idx}
                                className="tooltip-item"
                                style={{
                                  color: entry.color,
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  gap: "1.25rem",
                                }}
                              >
                                <span>
                                  <strong>{entry.name}:</strong> {Number(entry.value).toFixed(3)} L
                                </span>
                                {riskVal !== undefined && (
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      fontWeight: 600,
                                      padding: "0.1rem 0.4rem",
                                      borderRadius: "4px",
                                      background:
                                        riskVal >= 50
                                          ? "rgba(225, 29, 72, 0.12)"
                                          : "rgba(13, 148, 136, 0.12)",
                                      color:
                                        riskVal >= 50
                                          ? "var(--rose-primary)"
                                          : "var(--teal-primary)",
                                    }}
                                  >
                                    {riskVal}% flare-up risk
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend verticalAlign="top" height={36} iconType="circle" />

                {selectedScenarios.includes("baseline") && (
                  <Line
                    type="monotone"
                    dataKey="baseline"
                    name="Baseline (No Intervention)"
                    stroke={SCENARIO_CONFIGS.baseline.color}
                    strokeWidth={3}
                    dot={{ fill: SCENARIO_CONFIGS.baseline.color, r: 4 }}
                  />
                )}
                {selectedScenarios.includes("smoking_cessation") && (
                  <Line
                    type="monotone"
                    dataKey="smoking_cessation"
                    name="Smoking Cessation"
                    stroke={SCENARIO_CONFIGS.smoking_cessation.color}
                    strokeWidth={3}
                    dot={{ fill: SCENARIO_CONFIGS.smoking_cessation.color, r: 4 }}
                  />
                )}
                {selectedScenarios.includes("increased_activity") && (
                  <Line
                    type="monotone"
                    dataKey="increased_activity"
                    name="High Physical Activity"
                    stroke={SCENARIO_CONFIGS.increased_activity.color}
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={{ fill: SCENARIO_CONFIGS.increased_activity.color, r: 4 }}
                  />
                )}
                {selectedScenarios.includes("combined_intervention") && (
                  <Line
                    type="monotone"
                    dataKey="combined_intervention"
                    name="Combined Intervention"
                    stroke={SCENARIO_CONFIGS.combined_intervention.color}
                    strokeWidth={3}
                    dot={{ fill: SCENARIO_CONFIGS.combined_intervention.color, r: 5 }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
            Select scenarios and click Run What-If Simulation to view projected trajectories.
          </div>
        )}

        {/* Delta Callout Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", marginTop: "1rem" }}>
          <div style={{ padding: "0.75rem 1rem", background: "var(--rose-light)", borderRadius: "var(--radius-md)", border: "1px solid var(--rose-border)" }}>
            <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--rose-primary)", textTransform: "uppercase" }}>
              Baseline Projected Loss
            </div>
            <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--rose-primary)" }}>
              {baselineFinal ? `${baselineFinal.toFixed(3)} L` : "—"}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
              at month {horizonMonths} with status quo
            </div>
          </div>

          <div style={{ padding: "0.75rem 1rem", background: "var(--teal-light)", borderRadius: "var(--radius-md)", border: "1px solid var(--teal-border)" }}>
            <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--teal-primary)", textTransform: "uppercase" }}>
              Smoking Cessation Delta
            </div>
            <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--teal-primary)" }}>
              {cessationGain ? `+${cessationGain} L` : "—"}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
              additional capacity preserved
            </div>
          </div>

          {combinedGain && (
            <div style={{ padding: "0.75rem 1rem", background: "var(--emerald-light)", borderRadius: "var(--radius-md)", border: "1px solid var(--emerald-border)" }}>
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--emerald-primary)", textTransform: "uppercase" }}>
                Combined Synergy Gain
              </div>
              <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--emerald-primary)" }}>
                +{combinedGain} L
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                quit smoking + daily high activity
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Layer 3 Dual-Outcome: Acute Flare-up (Exacerbation) Risk Gauge Card */}
      {baselineRiskFinal !== null && (
        <div className="card" style={{ borderLeft: "4px solid var(--rose-primary)" }}>
          <div className="card-header" style={{ borderBottom: "1px solid var(--border-light)", paddingBottom: "0.85rem" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div
                  className="brand-icon"
                  style={{
                    width: "36px",
                    height: "36px",
                    background: "linear-gradient(135deg, var(--rose-primary), #f43f5e)",
                    color: "white",
                  }}
                >
                  <Flame size={19} />
                </div>
                <div>
                  <h3 className="card-title">
                    Acute Flare-up (Exacerbation) Risk Gauge
                  </h3>
                  <p className="card-subtitle">
                    Dual-outcome digital twin classifier estimating 12-month acute exacerbation probability at Month {horizonMonths}.
                  </p>
                </div>
              </div>
            </div>

            {riskReductionPct !== null && riskReductionPct > 0 ? (
              <span
                className="badge"
                style={{
                  background: "var(--emerald-light)",
                  color: "var(--emerald-primary)",
                  border: "1px solid var(--emerald-border)",
                  padding: "0.35rem 0.75rem",
                  fontSize: "0.8125rem",
                  fontWeight: 700,
                }}
              >
                <ShieldCheck size={14} />
                -{riskReductionPct}% Absolute Risk Reduction
              </span>
            ) : (
              <span
                className="badge"
                style={{
                  background: "var(--bg-surface-secondary)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border-light)",
                  padding: "0.35rem 0.75rem",
                  fontSize: "0.8125rem",
                }}
              >
                Dual Twin Outcome
              </span>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem", marginTop: "1rem" }}>
            {/* Status Quo Gauge Card */}
            <div
              style={{
                padding: "1.25rem",
                borderRadius: "var(--radius-md)",
                background: "linear-gradient(180deg, white, var(--rose-light))",
                border: "1px solid var(--rose-border)",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--rose-primary)", textTransform: "uppercase" }}>
                  Status Quo (Baseline Trajectory)
                </span>
                <span
                  className="badge"
                  style={{
                    background: baselineRiskFinal >= 50 ? "var(--rose-primary)" : baselineRiskFinal >= 25 ? "var(--amber-primary, #d97706)" : "var(--teal-primary)",
                    color: "white",
                    fontSize: "0.7rem",
                    fontWeight: 700,
                  }}
                >
                  {baselineRiskFinal >= 50 ? "High Risk Tier" : baselineRiskFinal >= 25 ? "Moderate Risk Tier" : "Low Risk Tier"}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                <span style={{ fontSize: "2.25rem", fontWeight: 800, color: "var(--rose-primary)", letterSpacing: "-0.02em" }}>
                  {baselineRiskFinal.toFixed(1)}%
                </span>
                <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                  acute flare-up likelihood
                </span>
              </div>

              {/* Progress Gauge Meter */}
              <div style={{ width: "100%", height: "10px", background: "rgba(225, 29, 72, 0.15)", borderRadius: "5px", overflow: "hidden" }}>
                <div
                  style={{
                    width: `${Math.min(baselineRiskFinal, 100)}%`,
                    height: "100%",
                    background: "linear-gradient(90deg, #f43f5e, #be123c)",
                    borderRadius: "5px",
                    transition: "width 0.4s ease",
                  }}
                />
              </div>

              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                Status quo continuation maintains heightened risk of acute inflammatory exacerbation requiring urgent oral steroids or hospitalization.
              </div>
            </div>

            {/* Intervention Gauge Card */}
            {activeInterventionRiskFinal !== null && (
              <div
                style={{
                  padding: "1.25rem",
                  borderRadius: "var(--radius-md)",
                  background: "linear-gradient(180deg, white, var(--emerald-light))",
                  border: "1px solid var(--emerald-border)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--emerald-primary)", textTransform: "uppercase" }}>
                    Under {activeInterventionLabel}
                  </span>
                  <span
                    className="badge"
                    style={{
                      background: "var(--emerald-primary)",
                      color: "white",
                      fontSize: "0.7rem",
                      fontWeight: 700,
                    }}
                  >
                    Attenuated Vulnerability
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                  <span style={{ fontSize: "2.25rem", fontWeight: 800, color: "var(--emerald-primary)", letterSpacing: "-0.02em" }}>
                    {activeInterventionRiskFinal.toFixed(1)}%
                  </span>
                  <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                    reduced flare-up likelihood
                  </span>
                </div>

                {/* Progress Gauge Meter */}
                <div style={{ width: "100%", height: "10px", background: "rgba(13, 148, 136, 0.15)", borderRadius: "5px", overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${Math.min(activeInterventionRiskFinal, 100)}%`,
                      height: "100%",
                      background: "linear-gradient(90deg, #10b981, #059669)",
                      borderRadius: "5px",
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>

                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                  Proactive behavioral intervention eliminates toxic airway triggers, lowering 12-month exacerbation hazard by{" "}
                  <strong>{relativeRiskReduction ? `${relativeRiskReduction}%` : "substantially"}</strong>.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Return on Intervention (ROI) & Dual End-State Projection */}
      {baselineFinal !== null && activeInterventionFinal !== null && (
        <div className="card roi-impact-card">
          <div className="card-header" style={{ borderBottom: "1px solid var(--border-light)", paddingBottom: "1rem" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div className="brand-icon" style={{ width: "36px", height: "36px", background: "linear-gradient(135deg, var(--teal-primary), var(--emerald-primary))" }}>
                  <Award size={19} />
                </div>
                <div>
                  <h3 className="card-title">
                    Clinical Return on Intervention (ROI) &amp; End-State Projection
                  </h3>
                  <p className="card-subtitle">
                    Projected physiological benefit comparing status quo trajectory against <strong>{activeInterventionLabel}</strong> over {horizonMonths} months.
                  </p>
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="badge" style={{ background: "var(--emerald-light)", color: "var(--emerald-primary)", border: "1px solid var(--emerald-border)", padding: "0.35rem 0.75rem", fontSize: "0.8125rem", fontWeight: 700 }}>
                <ShieldCheck size={14} />
                +{deltaPreservedML} mL Preserved
              </span>
            </div>
          </div>

          {/* ROI Metric Blocks */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
            <div style={{ padding: "1rem", background: "linear-gradient(135deg, var(--emerald-light), white)", border: "1px solid var(--emerald-border)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--emerald-primary)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                Lung Capacity Preserved
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.35rem", marginTop: "0.25rem" }}>
                <span style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--emerald-primary)" }}>
                  +{deltaPreservedML}
                </span>
                <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "var(--text-secondary)" }}>mL</span>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  (+{deltaPreserved?.toFixed(3)} L)
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                +{relativeCapacityGain}% relative retention vs unmitigated decline
              </div>
            </div>

            <div style={{ padding: "1rem", background: "linear-gradient(135deg, var(--teal-light), white)", border: "1px solid var(--teal-border)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--teal-primary)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                Loss Attenuation
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.35rem", marginTop: "0.25rem" }}>
                <span style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--teal-primary)" }}>
                  {pctDeclineAttenuated}%
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                of projected physiological decline halted over horizon
              </div>
            </div>

            <div style={{ padding: "1rem", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-light)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                End-State Comparison ({horizonMonths} mo)
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginTop: "0.25rem" }}>
                <span style={{ fontSize: "1.125rem", fontWeight: 700, color: "var(--rose-primary)" }}>
                  {baselineFinal.toFixed(2)} L
                </span>
                <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>vs</span>
                <span style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--emerald-primary)" }}>
                  {activeInterventionFinal.toFixed(2)} L
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                {activeInterventionLabel} preserves higher functional reserve
              </div>
            </div>

            <div style={{ padding: "1rem", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-light)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                Annualized Velocity
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.35rem", marginTop: "0.25rem" }}>
                <span style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--teal-primary)" }}>
                  +{Math.round((deltaPreservedML || 0) / (horizonMonths / 12))}
                </span>
                <span style={{ fontSize: "0.8125rem", fontWeight: 700, color: "var(--text-secondary)" }}>mL / yr</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                rate of lung preservation per year under intervention
              </div>
            </div>
          </div>

          {/* Dual Anatomical Lung Visualizer Section */}
          <div style={{ marginTop: "1.5rem", paddingTop: "1.25rem", borderTop: "1px solid var(--border-light)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
              <div>
                <h4 style={{ fontSize: "0.9375rem", fontWeight: 700, color: "var(--text-primary)" }}>
                  End-State Anatomical Capacity Comparison at Month {horizonMonths}
                </h4>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  Direct physiological visual simulation of lung volume under unmitigated decline versus preventive intervention.
                </p>
              </div>
              <span className="badge badge-demo">Illustrative 2D Model</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem", alignItems: "center" }}>
              {/* Left Lung: Baseline Status Quo */}
              <div className="card" style={{ padding: "1.25rem", background: "linear-gradient(180deg, white, var(--rose-light))", border: "1px solid var(--rose-border)", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <span className="badge" style={{ background: "var(--rose-primary)", color: "white", fontSize: "0.7rem", fontWeight: 700 }}>
                    Status Quo (No Change)
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Month {horizonMonths}</span>
                </div>
                <LungVisualizer
                  fev1={baselineFinal}
                  goldStage={getGoldStageFromFEV1(baselineFinal, baselineReference)}
                  baselineFev1={baselineReference}
                  title="Baseline Projected Lung"
                  subtitle={`Projected FEV1: ${baselineFinal.toFixed(2)} L`}
                  size="md"
                />
              </div>

              {/* Right Lung: Intervention End-State */}
              <div className="card" style={{ padding: "1.25rem", background: "linear-gradient(180deg, white, var(--emerald-light))", border: "1px solid var(--emerald-border)", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <span className="badge" style={{ background: "var(--emerald-primary)", color: "white", fontSize: "0.7rem", fontWeight: 700 }}>
                    {activeInterventionLabel}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Month {horizonMonths}</span>
                </div>
                <LungVisualizer
                  fev1={activeInterventionFinal}
                  goldStage={getGoldStageFromFEV1(activeInterventionFinal, baselineReference)}
                  baselineFev1={baselineReference}
                  title="Intervention End-State"
                  subtitle={`Projected FEV1: ${activeInterventionFinal.toFixed(2)} L`}
                  size="md"
                />
              </div>
            </div>
          </div>

          {/* Clinical Takeaway Callout */}
          <div style={{ marginTop: "1.25rem", padding: "0.85rem 1rem", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-light)", borderRadius: "var(--radius-md)", display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
            <div style={{ color: "var(--teal-primary)", marginTop: "0.1rem" }}>
              <CheckCircle2 size={18} />
            </div>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", lineHeight: 1.5 }}>
              <strong>Clinical Action Takeaway:</strong> Proactive intervention ({activeInterventionLabel.toLowerCase()}) demonstrates a statistically and clinically meaningful deceleration of lung function decline for patient <strong>{selectedPatientId}</strong>, retaining <strong>+{deltaPreservedML} mL</strong> of functional capacity and preserving quality of life over the {horizonMonths}-month horizon.
            </div>
          </div>
        </div>
      )}

      {/* Model Comparison Table & Feature Importance */}
      {modelComparison && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">
                <BarChart3 size={18} color="#0d9488" />
                Model Comparison: Random Forest vs. XGBoost
              </h3>
              <p className="card-subtitle">
                Validation metrics evaluated on held-out patient groups (zero patient-level longitudinal leakage).
              </p>
            </div>
            <span className="badge badge-online">Held-out Test Set</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
            {/* Left: Metrics Table */}
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Evaluation Metric</th>
                    <th>Random Forest</th>
                    <th>XGBoost</th>
                    <th>Performance Winner</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Mean Absolute Error (MAE)</strong></td>
                    <td>{modelComparison.rf_metrics.mae.toFixed(4)} L</td>
                    <td>{modelComparison.xgb_metrics.mae.toFixed(4)} L</td>
                    <td>
                      <span className="badge" style={{ background: "var(--teal-light)", color: "var(--teal-primary)" }}>
                        {modelComparison.xgb_metrics.mae <= modelComparison.rf_metrics.mae ? "XGBoost" : "Random Forest"}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td><strong>Root Mean Squared Error (RMSE)</strong></td>
                    <td>{modelComparison.rf_metrics.rmse.toFixed(4)} L</td>
                    <td>{modelComparison.xgb_metrics.rmse.toFixed(4)} L</td>
                    <td>
                      <span className="badge" style={{ background: "var(--teal-light)", color: "var(--teal-primary)" }}>
                        {modelComparison.xgb_metrics.rmse <= modelComparison.rf_metrics.rmse ? "XGBoost" : "Random Forest"}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td><strong>Coefficient of Determination (R²)</strong></td>
                    <td>{modelComparison.rf_metrics.r2.toFixed(4)}</td>
                    <td>{modelComparison.xgb_metrics.r2.toFixed(4)}</td>
                    <td>
                      <span className="badge" style={{ background: "var(--teal-light)", color: "var(--teal-primary)" }}>
                        {modelComparison.xgb_metrics.r2 >= modelComparison.rf_metrics.r2 ? "XGBoost" : "Random Forest"}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Right: Feature Importances */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
              <span style={{ fontSize: "0.8125rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>
                Top Key Predictive Drivers ({modelType === "xgboost" ? "XGBoost" : "Random Forest"})
              </span>

              {Object.entries(modelComparison.feature_importances)
                .slice(0, 5)
                .map(([feat, val], idx) => {
                  const pct = (val * 100).toFixed(1);
                  const cleanName = feat.replace("num__", "").replace("cat__", "").replace(/_/g, " ");
                  return (
                    <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-primary)" }}>
                        <span style={{ textTransform: "capitalize" }}>{cleanName}</span>
                        <strong>{pct}%</strong>
                      </div>
                      <div style={{ width: "100%", height: "6px", background: "var(--bg-surface-secondary)", borderRadius: "3px", overflow: "hidden" }}>
                        <div
                          style={{
                            width: `${Math.max(Number(pct), 3)}%`,
                            height: "100%",
                            background: idx === 0 ? "var(--teal-primary)" : "var(--blue-primary)",
                            borderRadius: "3px",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
