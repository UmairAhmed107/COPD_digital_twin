"use client";

import React, { useState, useMemo } from "react";
import {
  X,
  PlusCircle,
  Activity,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Sparkles,
  User,
} from "lucide-react";
import { createPatient } from "../lib/api";
import { CreatePatientRequest, TwinStateResponse } from "../lib/types";

interface CreateTwinModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newTwin: TwinStateResponse) => void;
}

export default function CreateTwinModal({
  isOpen,
  onClose,
  onSuccess,
}: CreateTwinModalProps) {
  const [patientId, setPatientId] = useState<string>("");
  const [sex, setSex] = useState<"M" | "F">("M");
  const [age, setAge] = useState<number>(64);
  const [fev1, setFev1] = useState<number>(1.85);
  const [fvc, setFvc] = useState<number>(3.10);
  const [smoking, setSmoking] = useState<string>("former");
  const [packYears, setPackYears] = useState<number>(32);
  const [bmi, setBmi] = useState<number>(26.4);
  const [activity, setActivity] = useState<string>("moderate");

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Live calculation of FEV1/FVC ratio and inferred GOLD stage
  const ratio = useMemo(() => {
    if (!fvc || fvc <= 0) return 0;
    return Math.round((fev1 / fvc) * 100) / 100;
  }, [fev1, fvc]);

  const inferredGoldStage = useMemo(() => {
    if (fev1 >= 2.5) return "I (Mild)";
    if (fev1 >= 1.7) return "II (Moderate)";
    if (fev1 >= 1.0) return "III (Severe)";
    return "IV (Very Severe)";
  }, [fev1]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (fev1 <= 0 || fvc <= 0) {
      setError("FEV1 and FVC must be positive numerical values.");
      return;
    }
    if (fvc < fev1) {
      setError("FVC (Forced Vital Capacity) cannot be less than FEV1.");
      return;
    }
    if (age < 18 || age > 105) {
      setError("Patient age must be between 18 and 105.");
      return;
    }

    setLoading(true);
    try {
      const payload: CreatePatientRequest = {
        patient_id: patientId.trim() || undefined,
        sex,
        age_at_baseline: Number(age),
        gold_stage_baseline: inferredGoldStage,
        smoking_status_baseline: smoking,
        pack_years: Number(packYears),
        baseline_fev1_liters: Number(fev1),
        baseline_fvc_liters: Number(fvc),
        baseline_fev1_fvc_ratio: ratio,
        bmi: Number(bmi),
        activity_level_baseline: activity,
      };

      const newTwin = await createPatient(payload);
      onSuccess(newTwin);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to initialize digital twin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(15, 23, 42, 0.65)",
        backdropFilter: "blur(6px)",
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        animation: "fadeIn 0.2s ease-out",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: "620px",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "2rem",
          background: "var(--bg-surface)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
          border: "1px solid var(--border-light)",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: "1.5rem",
            borderBottom: "1px solid var(--border-light)",
            paddingBottom: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div
              className="brand-icon"
              style={{
                width: "42px",
                height: "42px",
                borderRadius: "var(--radius-md)",
                background: "linear-gradient(135deg, var(--teal-primary), var(--blue-primary))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "white",
              }}
            >
              <PlusCircle size={22} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)" }}>
                Create Digital Twin
              </h2>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                Initialize baseline vitals and persist a new patient twin to the SQLite database.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            style={{
              border: "none",
              background: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              padding: "0.25rem",
              borderRadius: "var(--radius-sm)",
            }}
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="alert-box alert-error" style={{ marginBottom: "1.25rem" }}>
            <AlertCircle size={18} />
            <div style={{ fontSize: "0.875rem" }}>{error}</div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Live Inferred Physiology Banner */}
          <div
            style={{
              background: "linear-gradient(135deg, var(--teal-light), var(--blue-light))",
              border: "1px solid var(--teal-border)",
              borderRadius: "var(--radius-md)",
              padding: "0.875rem 1rem",
              marginBottom: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--teal-primary)", textTransform: "uppercase" }}>
                Auto-Inferred Classification
              </span>
              <div style={{ display: "flex", gap: "1rem", marginTop: "0.25rem", fontSize: "0.875rem" }}>
                <span>
                  GOLD Stage: <strong>{inferredGoldStage}</strong>
                </span>
                <span>
                  FEV1/FVC Ratio: <strong>{ratio.toFixed(2)}</strong>
                </span>
              </div>
            </div>
            <span className="badge badge-online">
              <Sparkles size={12} /> Auto-Calibrated
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {/* Patient ID */}
            <div>
              <label className="form-label">
                Patient Identifier <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(Optional)</span>
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="Auto-assigned (e.g. P0101)"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
              />
            </div>

            {/* Sex */}
            <div>
              <label className="form-label">Biological Sex</label>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  className={`tab-button ${sex === "M" ? "active" : ""}`}
                  style={{ flex: 1, padding: "0.5rem", justifyContent: "center" }}
                  onClick={() => setSex("M")}
                >
                  Male (M)
                </button>
                <button
                  type="button"
                  className={`tab-button ${sex === "F" ? "active" : ""}`}
                  style={{ flex: 1, padding: "0.5rem", justifyContent: "center" }}
                  onClick={() => setSex("F")}
                >
                  Female (F)
                </button>
              </div>
            </div>

            {/* Baseline Age */}
            <div>
              <label className="form-label">Baseline Age (years)</label>
              <input
                type="number"
                className="form-input"
                min="18"
                max="105"
                value={age}
                onChange={(e) => setAge(Number(e.target.value))}
                required
              />
            </div>

            {/* Baseline BMI */}
            <div>
              <label className="form-label">Body Mass Index (BMI)</label>
              <input
                type="number"
                step="0.1"
                className="form-input"
                min="12"
                max="60"
                value={bmi}
                onChange={(e) => setBmi(Number(e.target.value))}
                required
              />
            </div>

            {/* Baseline FEV1 */}
            <div>
              <label className="form-label">Baseline FEV1 (Liters)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                min="0.4"
                max="5.5"
                value={fev1}
                onChange={(e) => setFev1(Number(e.target.value))}
                required
              />
            </div>

            {/* Baseline FVC */}
            <div>
              <label className="form-label">Baseline FVC (Liters)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                min="0.8"
                max="7.0"
                value={fvc}
                onChange={(e) => setFvc(Number(e.target.value))}
                required
              />
            </div>

            {/* Smoking Status */}
            <div>
              <label className="form-label">Smoking Status</label>
              <select
                className="form-select"
                value={smoking}
                onChange={(e) => setSmoking(e.target.value)}
              >
                <option value="former">Former Smoker</option>
                <option value="current">Current Smoker</option>
                <option value="never">Never Smoked</option>
              </select>
            </div>

            {/* Pack-Years */}
            <div>
              <label className="form-label">Cumulative Pack-Years</label>
              <input
                type="number"
                step="0.5"
                className="form-input"
                min="0"
                max="150"
                value={packYears}
                onChange={(e) => setPackYears(Number(e.target.value))}
                required
              />
            </div>
          </div>

          {/* Activity Level */}
          <div style={{ marginTop: "1rem" }}>
            <label className="form-label">Baseline Activity Level</label>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              {["low", "moderate", "high"].map((act) => (
                <button
                  key={act}
                  type="button"
                  className={`tab-button ${activity === act ? "active" : ""}`}
                  style={{ flex: 1, padding: "0.5rem", justifyContent: "center", textTransform: "capitalize" }}
                  onClick={() => setActivity(act)}
                >
                  {act} Activity
                </button>
              ))}
            </div>
          </div>

          {/* Modal Footer Actions */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "0.75rem",
              marginTop: "1.75rem",
              paddingTop: "1.25rem",
              borderTop: "1px solid var(--border-light)",
            }}
          >
            <button
              type="button"
              className="tab-button"
              onClick={onClose}
              disabled={loading}
              style={{ padding: "0.6rem 1.25rem" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.6rem 1.5rem",
                background: "linear-gradient(135deg, var(--teal-primary), var(--blue-primary))",
                color: "white",
                border: "none",
                borderRadius: "var(--radius-md)",
                fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  Saving to SQLite...
                </>
              ) : (
                <>
                  <PlusCircle size={16} />
                  Initialize Digital Twin
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
