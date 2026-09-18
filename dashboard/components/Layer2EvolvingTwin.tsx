"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity,
  PlusCircle,
  Clock,
  User,
  Calendar,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  ChevronRight,
  Sparkles,
  MessageSquare,
  Bot,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { addPatientVisit, getPatient, getPatients, getTwinExplanation } from "../lib/api";
import { AddVisitRequest, ExplainResponse, PatientSummary, TwinStateResponse } from "../lib/types";
import AskTheTwinDrawer from "./AskTheTwinDrawer";
import LungVisualizer from "./LungVisualizer";
import AuditTrail, { generateClinicalNote } from "./AuditTrail";
import VitalityCommandCenter from "./VitalityCommandCenter";
import { useToast } from "../context/ToastContext";

interface Layer2EvolvingTwinProps {
  selectedPatientId: string;
  onSelectPatientId: (id: string) => void;
  onTwinStateChange?: (twin: TwinStateResponse) => void;
}

export default function Layer2EvolvingTwin({
  selectedPatientId,
  onSelectPatientId,
  onTwinStateChange,
}: Layer2EvolvingTwinProps) {
  const { showToast } = useToast();
  const [patientList, setPatientList] = useState<PatientSummary[]>([]);
  const [twinState, setTwinState] = useState<TwinStateResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [latestClinicalNote, setLatestClinicalNote] = useState<string | null>(null);

  // Keep ref for onTwinStateChange callback to prevent infinite re-render cycles
  const onTwinStateChangeRef = useRef(onTwinStateChange);
  useEffect(() => {
    onTwinStateChangeRef.current = onTwinStateChange;
  }, [onTwinStateChange]);

  // Gemini Narrative Layer state
  const [aiSummary, setAiSummary] = useState<ExplainResponse | null>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [showChatDrawer, setShowChatDrawer] = useState<boolean>(false);

  // Add Visit form state
  const [showAddVisit, setShowAddVisit] = useState<boolean>(false);
  const [submittingVisit, setSubmittingVisit] = useState<boolean>(false);
  const [addVisitSuccess, setAddVisitSuccess] = useState<string | null>(null);
  const [visitForm, setVisitForm] = useState<AddVisitRequest>({
    visit_number: 1,
    months_since_baseline: 6.0,
    age_at_visit: 65.5,
    smoking_status_at_visit: "former",
    activity_level_at_visit: "moderate",
    fev1_liters: 1.85,
    fvc_liters: 3.10,
    fev1_fvc_ratio: 0.60,
    exacerbations_this_visit: 0,
    measurement_source: "clinic",
  });

  // Fetch patient list on mount
  useEffect(() => {
    let mounted = true;
    async function loadPatients() {
      try {
        const patients = await getPatients();
        if (mounted) {
          setPatientList(patients);
        }
      } catch (err: any) {
        if (mounted) setError("Failed to load patient directory.");
      }
    }
    loadPatients();
    return () => {
      mounted = false;
    };
  }, []);

  // Fetch twin state when selectedPatientId changes (strictly depends only on selectedPatientId)
  useEffect(() => {
    if (!selectedPatientId) return;
    let mounted = true;
    setLoading(true);
    setError(null);
    setAddVisitSuccess(null);

    async function loadTwin() {
      try {
        const data = await getPatient(selectedPatientId);
        if (mounted) {
          setTwinState(data);
          onTwinStateChangeRef.current?.(data);

          // Pre-populate Add Visit form with reasonable increments
          const lastVisit = data.current;
          const nextVisitNum = (lastVisit?.visit_number || data.history.length || 0) + 1;
          const nextMonths = Math.round(((lastVisit?.months_since_baseline || 0) + 6.0) * 10) / 10;
          const nextAge = Math.round(((lastVisit?.age_at_visit || 65.0) + 0.5) * 10) / 10;
          const lastFEV1 = Number(lastVisit?.fev1_liters || 1.8);

          setVisitForm({
            visit_number: nextVisitNum,
            months_since_baseline: nextMonths,
            age_at_visit: nextAge,
            smoking_status_at_visit: lastVisit?.smoking_status_at_visit || "former",
            activity_level_at_visit: lastVisit?.activity_level_at_visit || "moderate",
            fev1_liters: Math.max(0.4, Math.round((lastFEV1 - 0.03) * 100) / 100),
            fvc_liters: Number(lastVisit?.fvc_liters || 3.0),
            fev1_fvc_ratio: Number(lastVisit?.fev1_fvc_ratio || 0.6),
            exacerbations_this_visit: 0,
            measurement_source: "clinic",
          });
        }
      } catch (err: any) {
        if (mounted) setError(err.message || "Failed to load twin state.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadTwin();

    return () => {
      mounted = false;
    };
  }, [selectedPatientId]);

  // Fetch AI Clinical Summary strictly when patientId changes or a new visit is added (history length changes)
  const historyLength = twinState?.history?.length || 0;
  useEffect(() => {
    if (!selectedPatientId || historyLength === 0) return;
    let mounted = true;

    async function loadAi() {
      setAiLoading(true);
      setAiError(null);
      try {
        const data = await getTwinExplanation(selectedPatientId);
        if (mounted) {
          setAiSummary(data);
        }
      } catch (err: any) {
        if (mounted) {
          setAiError(err.message || "Failed to generate AI clinical summary.");
        }
      } finally {
        if (mounted) {
          setAiLoading(false);
        }
      }
    }

    loadAi();

    return () => {
      mounted = false;
    };
  }, [selectedPatientId, historyLength]);

  // Manual refresh handler for user interaction
  const fetchAiSummary = useCallback(async (patientId: string) => {
    if (!patientId) return;
    setAiLoading(true);
    setAiError(null);
    try {
      const data = await getTwinExplanation(patientId);
      setAiSummary(data);
    } catch (err: any) {
      setAiError(err.message || "Failed to generate AI clinical summary.");
    } finally {
      setAiLoading(false);
    }
  }, []);

  const handleAddVisitSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) return;
    setSubmittingVisit(true);
    setError(null);

    try {
      const updatedTwin = await addPatientVisit(selectedPatientId, visitForm);
      setTwinState(updatedTwin);
      onTwinStateChangeRef.current?.(updatedTwin);

      // Generate automated plain-English clinical note for the newly recorded visit
      const historyLen = updatedTwin.history.length;
      const currentVisit = updatedTwin.history[historyLen - 1];
      const prevVisit = historyLen > 1 ? updatedTwin.history[historyLen - 2] : null;
      const note = generateClinicalNote(
        currentVisit,
        prevVisit,
        Number(updatedTwin.static.baseline_fev1_liters || 2.0)
      );

      setLatestClinicalNote(note);
      setAddVisitSuccess(note);
      setShowAddVisit(false);

      // Live Alert Feed: trigger high-contrast toast if clinical thresholds are breached
      const exacCount = Number(visitForm.exacerbations_this_visit || 0);
      const fev1Val = Number(visitForm.fev1_liters);

      if (exacCount > 0) {
        showToast({
          type: "critical",
          title: "⚠️ Acute Exacerbation Documented",
          message: `Visit #${visitForm.visit_number} logged ${exacCount} acute flare-up event. High risk protocol triggered.`,
        });
      } else if (fev1Val <= 0.90) {
        showToast({
          type: "critical",
          title: "⚠️ Critical Alert: GOLD Stage IV",
          message: `Observed FEV1 fell to ${fev1Val.toFixed(2)}L, entering Stage IV severe airflow limitation.`,
        });
      } else {
        showToast({
          type: "success",
          title: `Clinical Memory: Visit #${visitForm.visit_number} Recorded`,
          message: note,
        });
      }

      // Increment form for next possible visit
      const nextNum = visitForm.visit_number + 1;
      const nextM = Math.round((visitForm.months_since_baseline + 6.0) * 10) / 10;
      const nextA = Math.round((visitForm.age_at_visit + 0.5) * 10) / 10;
      setVisitForm((prev) => ({
        ...prev,
        visit_number: nextNum,
        months_since_baseline: nextM,
        age_at_visit: nextA,
      }));
    } catch (err: any) {
      setError(err.message || "Failed to add new visit.");
    } finally {
      setSubmittingVisit(false);
    }
  };

  // Prepare chart data from history
  const chartData = (twinState?.history || []).map((v) => ({
    month: v.months_since_baseline,
    fev1: Number(v.fev1_liters),
    visitNumber: v.visit_number,
    fvc: Number(v.fvc_liters || 0),
    ratio: Number(v.fev1_fvc_ratio || 0),
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Patient Picker Top Bar */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div className="brand-icon" style={{ width: "36px", height: "36px", background: "var(--teal-primary)" }}>
              <User size={18} />
            </div>
            <div>
              <label htmlFor="patient-select-dropdown" className="form-label" style={{ marginBottom: "0.15rem" }}>
                Patient Digital Twin Selector
              </label>
              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Switch between synthetic patients to inspect longitudinal evolving states.
              </p>
            </div>
          </div>

          <div style={{ minWidth: "320px", flex: 1, maxWidth: "520px" }}>
            <select
              id="patient-select-dropdown"
              className="form-select"
              value={selectedPatientId}
              onChange={(e) => onSelectPatientId(e.target.value)}
            >
              {patientList.length > 0 ? (
                patientList.slice(0, 50).map((p) => (
                  <option key={p.patient_id} value={p.patient_id}>
                    {p.patient_id} — {p.summary}
                  </option>
                ))
              ) : (
                <option value={selectedPatientId}>{selectedPatientId} (Loading...)</option>
              )}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert-box alert-error">
          <AlertCircle size={18} />
          <div>{error}</div>
        </div>
      )}

      {addVisitSuccess && (
        <div className="alert-box" style={{ background: "var(--emerald-light)", border: "1px solid var(--emerald-border)", color: "var(--emerald-primary)" }}>
          <CheckCircle2 size={18} />
          <div>{addVisitSuccess}</div>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 0.5rem" }} />
          Loading Patient Digital Twin State...
        </div>
      ) : twinState ? (
        <>
          {/* Vitality Command Center Header */}
          <VitalityCommandCenter
            patientId={twinState.patient_id}
            refreshKey={twinState.history.length}
          />

          {/* Twin Profile Overview Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            {/* Card 1: Static Demographics */}
            <div className="card" style={{ padding: "1.25rem" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                Static Baseline Identity
              </span>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)", marginTop: "0.25rem" }}>
                {twinState.patient_id}
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", marginTop: "0.75rem", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                <div><strong>Sex:</strong> {twinState.static.sex === "M" ? "Male" : "Female"}</div>
                <div><strong>Baseline Age:</strong> {twinState.static.age_at_baseline || twinState.history[0]?.age_at_visit} years</div>
                <div><strong>GOLD Stage Baseline:</strong> {twinState.static.gold_stage_baseline}</div>
                <div><strong>Baseline FEV1:</strong> {twinState.static.baseline_fev1_liters} L</div>
                <div><strong>Pack-Years:</strong> {twinState.static.pack_years}</div>
              </div>
            </div>

            {/* Card 2: Current State */}
            <div className="card" style={{ padding: "1.25rem", background: "linear-gradient(135deg, var(--teal-light), white)", borderColor: "var(--teal-border)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--teal-primary)", textTransform: "uppercase" }}>
                  Current Observation State
                </span>
                <span className="badge badge-demo">Visit #{twinState.current.visit_number}</span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.375rem", marginTop: "0.5rem" }}>
                <span style={{ fontSize: "2rem", fontWeight: 800, color: "var(--teal-primary)" }}>
                  {Number(twinState.current.fev1_liters).toFixed(2)}
                </span>
                <span style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-secondary)" }}>Liters</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", marginTop: "0.5rem", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                <div><strong>Months Elapsed:</strong> {twinState.current.months_since_baseline} mo</div>
                <div><strong>Smoking Status:</strong> <span style={{ textTransform: "capitalize" }}>{twinState.current.smoking_status_at_visit}</span></div>
                <div><strong>Activity Level:</strong> <span style={{ textTransform: "capitalize" }}>{twinState.current.activity_level_at_visit}</span></div>
                <div><strong>Measurement Source:</strong> {twinState.current.measurement_source}</div>
              </div>
            </div>

            {/* Card 3: Progression Summary */}
            <div className="card" style={{ padding: "1.25rem" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                Longitudinal Progression
              </span>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.375rem", marginTop: "0.5rem" }}>
                <span style={{ fontSize: "2rem", fontWeight: 800, color: Number(twinState.current.fev1_liters) - Number(twinState.static.baseline_fev1_liters) < 0 ? "var(--rose-primary)" : "var(--emerald-primary)" }}>
                  {(Number(twinState.current.fev1_liters) - Number(twinState.static.baseline_fev1_liters)).toFixed(2)}
                </span>
                <span style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-secondary)" }}>L total change</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", marginTop: "0.5rem", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                <div><strong>Recorded Visits:</strong> {twinState.history.length} observations</div>
                <div><strong>Current Age:</strong> {twinState.current.age_at_visit} years</div>
                <div><strong>Total Exacerbations:</strong> {twinState.history.reduce((acc, v) => acc + (v.exacerbations_this_visit || 0), 0)}</div>
                <div style={{ marginTop: "0.25rem" }}>
                  <button
                    id="toggle-add-visit-btn"
                    type="button"
                    className="btn btn-primary"
                    style={{ width: "100%", padding: "0.4rem 0.75rem", fontSize: "0.8125rem" }}
                    onClick={() => setShowAddVisit(!showAddVisit)}
                  >
                    <PlusCircle size={15} />
                    {showAddVisit ? "Cancel New Visit" : "Add Clinical Visit"}
                  </button>
                </div>
              </div>
            </div>

            {/* Card 4: 2D Anatomical Lung Capacity Gauge */}
            <div className="card" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <LungVisualizer
                fev1={Number(twinState.current.fev1_liters)}
                goldStage={twinState.static.gold_stage_baseline || "II"}
                baselineFev1={Number(twinState.static.baseline_fev1_liters)}
                title="Physiological Capacity"
                subtitle="Observed FEV1 vs 3.5L reference"
                size="sm"
              />
            </div>
          </div>

          {/* AI Clinical Summary Card (Gemini Narrative Layer) */}
          <div className="ai-summary-card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem", borderBottom: "1px solid var(--border-light)", paddingBottom: "1rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <div className="brand-icon" style={{ width: "38px", height: "38px", background: "linear-gradient(135deg, var(--teal-primary), var(--blue-primary))" }}>
                  <Sparkles size={20} />
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    <h3 style={{ fontSize: "1.125rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      AI Clinical Summary
                    </h3>
                    <span className="ai-badge">
                      <span className="ai-badge-pulse" />
                      Gemini Grounded Pulmonologist
                    </span>
                  </div>
                  <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "0.15rem" }}>
                    Automated clinical narrative translating trajectory data, risk drivers, and intervention benefits.
                  </p>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "0.45rem 0.85rem", fontSize: "0.8125rem" }}
                  onClick={() => fetchAiSummary(selectedPatientId)}
                  disabled={aiLoading}
                  title="Re-run Gemini analysis for this patient"
                >
                  <RefreshCw size={14} className={aiLoading ? "animate-spin" : ""} />
                  {aiLoading ? "Analyzing..." : "Refresh Summary"}
                </button>

                <button
                  id="open-ask-twin-drawer-btn"
                  type="button"
                  className="btn btn-primary"
                  style={{ padding: "0.45rem 0.95rem", fontSize: "0.8125rem" }}
                  onClick={() => setShowChatDrawer(true)}
                >
                  <MessageSquare size={14} />
                  Ask the Twin
                </button>
              </div>
            </div>

            {/* Card Content */}
            {aiLoading ? (
              <div style={{ padding: "2.5rem 1rem", textAlign: "center", color: "var(--text-secondary)" }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 0.75rem", color: "var(--teal-primary)" }} />
                <div style={{ fontWeight: 600, fontSize: "0.9375rem" }}>Generating Data-Grounded Pulmonary Narrative...</div>
                <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  Ingesting baseline demographics, longitudinal visits, and simulating 24-month trajectory scenarios.
                </p>
              </div>
            ) : aiError ? (
              <div style={{ marginTop: "1rem" }}>
                <div className="alert-box alert-error" style={{ marginBottom: "0.5rem" }}>
                  <AlertCircle size={18} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>Unable to generate AI narrative</div>
                    <div style={{ fontSize: "0.8125rem", marginTop: "0.2rem" }}>{aiError}</div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}
                    onClick={() => fetchAiSummary(selectedPatientId)}
                  >
                    Retry
                  </button>
                </div>
                {aiError.includes("GEMINI_API_KEY") && (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", padding: "0 0.5rem" }}>
                    Tip: Set the <code>GEMINI_API_KEY</code> environment variable on your server before running the FastAPI backend.
                  </div>
                )}
              </div>
            ) : aiSummary ? (
              <div>
                {/* 3-Bullet Summary */}
                <div className="ai-bullets-list">
                  {aiSummary.summary_bullets.map((bullet, idx) => (
                    <div key={idx} className="ai-bullet-item">
                      <div className="ai-bullet-icon">
                        <CheckCircle2 size={15} />
                      </div>
                      <div>
                        {bullet}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Clinical Risk Rationale Callout */}
                {aiSummary.risk_rationale && (
                  <div className="ai-rationale-box">
                    <div className="ai-rationale-title">
                      <Activity size={14} />
                      Clinical Risk Rationale &amp; Progression Drivers
                    </div>
                    <div className="ai-rationale-text">
                      {aiSummary.risk_rationale}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: "1.5rem 1rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                No clinical summary generated yet. Click &quot;Refresh Summary&quot; to analyze patient progression.
              </div>
            )}
          </div>

          {/* Clinical Audit Trail & Longitudinal Entry Section */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: "1.5rem", alignItems: "start" }}>
            <AuditTrail
              history={twinState.history}
              baselineFEV1={Number(twinState.static.baseline_fev1_liters)}
              patientId={twinState.patient_id}
              latestNote={latestClinicalNote}
            />

            {showAddVisit ? (
              <div className="card" style={{ borderColor: "var(--teal-primary)", background: "var(--teal-light)" }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title" style={{ color: "var(--teal-primary)" }}>
                      <PlusCircle size={18} />
                      Record New Clinical Visit (Add Visit)
                    </h3>
                    <p className="card-subtitle">
                      Appends a newly observed observation, mutating the twin&apos;s history and updating current state.
                    </p>
                  </div>
                </div>

                <form onSubmit={handleAddVisitSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Visit Number</label>
                      <input
                        type="number"
                        className="form-input"
                        value={visitForm.visit_number}
                        onChange={(e) => setVisitForm({ ...visitForm, visit_number: Number(e.target.value) })}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Months Since Baseline</label>
                      <input
                        type="number"
                        step="0.5"
                        className="form-input"
                        value={visitForm.months_since_baseline}
                        onChange={(e) => setVisitForm({ ...visitForm, months_since_baseline: Number(e.target.value) })}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Age at Visit</label>
                      <input
                        type="number"
                        step="0.5"
                        className="form-input"
                        value={visitForm.age_at_visit}
                        onChange={(e) => setVisitForm({ ...visitForm, age_at_visit: Number(e.target.value) })}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Observed FEV1 (L)</label>
                      <input
                        type="number"
                        step="0.01"
                        min="0.3"
                        max="5.5"
                        className="form-input"
                        value={visitForm.fev1_liters}
                        onChange={(e) => setVisitForm({ ...visitForm, fev1_liters: Number(e.target.value) })}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Smoking Status</label>
                      <select
                        className="form-select"
                        value={visitForm.smoking_status_at_visit}
                        onChange={(e) => setVisitForm({ ...visitForm, smoking_status_at_visit: e.target.value })}
                      >
                        <option value="never">Never Smoker</option>
                        <option value="former">Former Smoker</option>
                        <option value="current">Current Smoker</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Physical Activity</label>
                      <select
                        className="form-select"
                        value={visitForm.activity_level_at_visit}
                        onChange={(e) => setVisitForm({ ...visitForm, activity_level_at_visit: e.target.value })}
                      >
                        <option value="low">Low (Sedentary)</option>
                        <option value="moderate">Moderate</option>
                        <option value="high">High (Active)</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">FVC (L)</label>
                      <input
                        type="number"
                        step="0.01"
                        className="form-input"
                        value={visitForm.fvc_liters}
                        onChange={(e) => setVisitForm({ ...visitForm, fvc_liters: Number(e.target.value) })}
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Exacerbations This Visit</label>
                      <input
                        type="number"
                        min="0"
                        max="5"
                        className="form-input"
                        value={visitForm.exacerbations_this_visit}
                        onChange={(e) => setVisitForm({ ...visitForm, exacerbations_this_visit: Number(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowAddVisit(false)}
                    >
                      Cancel
                    </button>
                    <button
                      id="submit-add-visit-btn"
                      type="submit"
                      className="btn btn-primary"
                      disabled={submittingVisit}
                    >
                      {submittingVisit ? "Recording Observation..." : "Submit & Update Twin"}
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="card" style={{ padding: "1.75rem", display: "flex", flexDirection: "column", justifyContent: "center", minHeight: "280px", background: "linear-gradient(135deg, #f8fafc, #f1f5f9)", border: "1px dashed var(--border-medium)" }}>
                <div style={{ textAlign: "center" }}>
                  <div className="brand-icon" style={{ width: "44px", height: "44px", background: "var(--teal-primary)", margin: "0 auto 1rem" }}>
                    <PlusCircle size={22} />
                  </div>
                  <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    Record Longitudinal Clinical Visit
                  </h4>
                  <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", maxWidth: "340px", margin: "0.5rem auto 1.25rem", lineHeight: 1.5 }}>
                    Record a new in-clinic spirometry observation to advance the twin&apos;s timeline, mutate physiological state, and update trajectory simulations.
                  </p>
                  <button
                    id="open-add-visit-panel-btn"
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setShowAddVisit(true)}
                  >
                    <PlusCircle size={15} />
                    Open Visit Entry Form
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Historical Trajectory Chart */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">
                  <Activity size={18} color="#0d9488" />
                  Observed FEV1 Longitudinal Trajectory
                </h3>
                <p className="card-subtitle">
                  Historical clinic measurements spanning {twinState.history.length} documented visits.
                </p>
              </div>
            </div>

            <div style={{ width: "100%", height: "260px" }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="month"
                    name="Months"
                    unit=" mo"
                    stroke="#94a3b8"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis
                    unit=" L"
                    domain={["dataMin - 0.2", "dataMax + 0.2"]}
                    stroke="#94a3b8"
                    fontSize={12}
                    tickLine={false}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const pt = payload[0].payload;
                        return (
                          <div className="custom-chart-tooltip">
                            <div className="tooltip-title">Visit #{pt.visitNumber} ({pt.month} mo)</div>
                            <div className="tooltip-item" style={{ color: "var(--teal-primary)" }}>
                              <strong>FEV1:</strong> {pt.fev1.toFixed(3)} L
                            </div>
                            {pt.fvc > 0 && (
                              <div className="tooltip-item" style={{ color: "var(--text-secondary)" }}>
                                <strong>FVC:</strong> {pt.fvc.toFixed(3)} L
                              </div>
                            )}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="fev1"
                    name="Observed FEV1"
                    stroke="#0d9488"
                    strokeWidth={3}
                    dot={{ fill: "#0d9488", r: 5 }}
                    activeDot={{ r: 7 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chronological History Table */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">
                  <Clock size={18} color="#0d9488" />
                  Chronological Visit History
                </h3>
                <p className="card-subtitle">
                  Audit log of all physical measurements recorded for patient {twinState.patient_id}.
                </p>
              </div>
            </div>

            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Visit #</th>
                    <th>Timeline (Months)</th>
                    <th>Age</th>
                    <th>FEV1 (Liters)</th>
                    <th>FVC (Liters)</th>
                    <th>FEV1/FVC Ratio</th>
                    <th>Smoking</th>
                    <th>Activity</th>
                    <th>Exacerbations</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {twinState.history.map((v, idx) => (
                    <tr key={idx}>
                      <td><strong>#{v.visit_number}</strong></td>
                      <td>{v.months_since_baseline} mo</td>
                      <td>{v.age_at_visit}y</td>
                      <td style={{ fontWeight: 700, color: "var(--teal-primary)" }}>
                        {Number(v.fev1_liters).toFixed(3)} L
                      </td>
                      <td>{v.fvc_liters ? Number(v.fvc_liters).toFixed(2) : "—"} L</td>
                      <td>{v.fev1_fvc_ratio ? Number(v.fev1_fvc_ratio).toFixed(2) : "—"}</td>
                      <td style={{ textTransform: "capitalize" }}>{v.smoking_status_at_visit}</td>
                      <td style={{ textTransform: "capitalize" }}>{v.activity_level_at_visit}</td>
                      <td>
                        {v.exacerbations_this_visit > 0 ? (
                          <span className="badge" style={{ background: "var(--rose-light)", color: "var(--rose-primary)" }}>
                            {v.exacerbations_this_visit}
                          </span>
                        ) : (
                          "0"
                        )}
                      </td>
                      <td>{v.measurement_source || "clinic"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}

      {/* Ask the Twin Slide-out Drawer */}
      <AskTheTwinDrawer
        isOpen={showChatDrawer}
        onClose={() => setShowChatDrawer(false)}
        patientId={selectedPatientId}
        twinState={twinState}
      />
    </div>
  );
}

