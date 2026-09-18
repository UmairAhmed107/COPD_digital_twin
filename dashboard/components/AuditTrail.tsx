"use client";

import React, { useState } from "react";
import {
  Clock,
  Activity,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Minus,
  ArrowDownUp,
  MapPin,
  Calendar,
  FileText,
  Sparkles,
} from "lucide-react";

export interface AuditTrailEntry {
  visit_number: number;
  months_since_baseline: number;
  age_at_visit: number;
  fev1_liters: number;
  fvc_liters?: number;
  fev1_fvc_ratio?: number;
  smoking_status_at_visit?: string;
  activity_level_at_visit?: string;
  exacerbations_this_visit?: number;
  measurement_source?: string;
  [key: string]: any;
}

export interface ProcessedAuditEntry extends AuditTrailEntry {
  index: number;
  currentFEV1: number;
  deltaFromPrev: number;
  deltaFromBaseline: number;
  hasExacerbation: boolean;
  isRapidDecliner: boolean;
  isCurrentSmoker: boolean;
  isHighActivity: boolean;
  clinicalNote: string;
}

export function generateClinicalNote(
  entry: AuditTrailEntry | Record<string, any>,
  prevEntry: AuditTrailEntry | Record<string, any> | null,
  baselineFEV1: number = 2.0
): string {
  const visitNum = entry.visit_number ?? 1;
  const currentFEV1 = Number(entry.fev1_liters);
  const exacerbations = Number(entry.exacerbations_this_visit || 0);

  if (visitNum === 1 || !prevEntry) {
    return `Baseline Anchor Established: Initial FEV1 calibrated at ${currentFEV1.toFixed(2)}L. Patient twin initialized with ${entry.smoking_status_at_visit || "former"} smoking profile and ${entry.activity_level_at_visit || "moderate"} physical activity.`;
  }

  const prevFEV1 = Number(prevEntry.fev1_liters);
  const delta = currentFEV1 - prevFEV1;

  let changeStr = "";
  if (Math.abs(delta) < 0.02) {
    changeStr = "FEV1 remained stable";
  } else if (delta < 0) {
    changeStr = `FEV1 decreased by ${Math.abs(delta).toFixed(2)}L`;
  } else {
    changeStr = `FEV1 improved by ${delta.toFixed(2)}L`;
  }

  // Risk shift determination
  let riskStr = "";
  if (currentFEV1 <= 0.90) {
    riskStr = "Risk shifted to Critical (GOLD Stage IV severe airflow obstruction)";
  } else if (exacerbations > 0) {
    riskStr = `Risk shifted to High (${exacerbations} acute flare-up event recorded)`;
  } else if (delta < -0.05) {
    riskStr = "Risk shifted to High (accelerated decline velocity)";
  } else if (delta < -0.02) {
    riskStr = "Risk shifted to Guarded (moderate progression)";
  } else if (delta > 0.02) {
    riskStr = "Risk profile improved (functional capacity gain)";
  } else {
    riskStr = "Risk profile stable (compensated maintenance)";
  }

  return `Visit ${visitNum} Processed: ${changeStr}. ${riskStr}.`;
}

interface AuditTrailProps {
  history: Array<AuditTrailEntry | Record<string, any>>;
  baselineFEV1?: number;
  patientId?: string;
  latestNote?: string | null;
}

export default function AuditTrail({
  history,
  baselineFEV1 = 2.0,
  patientId,
  latestNote,
}: AuditTrailProps) {
  const [reverseOrder, setReverseOrder] = useState<boolean>(true);

  if (!history || history.length === 0) {
    return (
      <div className="card" style={{ padding: "1.5rem", textAlign: "center", color: "var(--text-muted)" }}>
        <Clock size={20} style={{ margin: "0 auto 0.5rem" }} />
        No clinical audit history recorded.
      </div>
    );
  }

  // Calculate deltas sequentially and generate plain-English clinical notes
  const entriesWithDeltas: ProcessedAuditEntry[] = history.map((visit, index) => {
    const prevVisit = index > 0 ? history[index - 1] : null;
    const currentFEV1 = Number(visit.fev1_liters);
    const prevFEV1 = prevVisit ? Number(prevVisit.fev1_liters) : Number(baselineFEV1);
    const deltaFromPrev = currentFEV1 - prevFEV1;
    const deltaFromBaseline = currentFEV1 - baselineFEV1;

    // Detect risk flags
    const hasExacerbation = Number(visit.exacerbations_this_visit || 0) > 0;
    const isRapidDecliner = deltaFromPrev < -0.05;
    const isCurrentSmoker = visit.smoking_status_at_visit === "current";
    const isHighActivity = visit.activity_level_at_visit === "high";

    const note = generateClinicalNote(visit as AuditTrailEntry, prevVisit as AuditTrailEntry, baselineFEV1);

    return {
      ...visit,
      visit_number: Number(visit.visit_number ?? index + 1),
      months_since_baseline: Number(visit.months_since_baseline ?? 0),
      age_at_visit: Number(visit.age_at_visit ?? 0),
      fev1_liters: currentFEV1,
      fvc_liters: visit.fvc_liters !== undefined ? Number(visit.fvc_liters) : undefined,
      fev1_fvc_ratio: visit.fev1_fvc_ratio !== undefined ? Number(visit.fev1_fvc_ratio) : undefined,
      smoking_status_at_visit: visit.smoking_status_at_visit || "former",
      activity_level_at_visit: visit.activity_level_at_visit || "moderate",
      exacerbations_this_visit: Number(visit.exacerbations_this_visit || 0),
      measurement_source: visit.measurement_source || "clinic",
      index,
      currentFEV1,
      deltaFromPrev,
      deltaFromBaseline,
      hasExacerbation,
      isRapidDecliner,
      isCurrentSmoker,
      isHighActivity,
      clinicalNote: note,
    };
  });

  const displayEntries = reverseOrder ? [...entriesWithDeltas].reverse() : entriesWithDeltas;

  return (
    <div className="card audit-trail-card">
      <div className="card-header" style={{ paddingBottom: "0.75rem", borderBottom: "1px solid var(--border-light)" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <h3 className="card-title">
              <Clock size={17} color="var(--teal-primary)" />
              Automated Clinical Audit Trail
            </h3>
            <span className="badge badge-demo">{history.length} Observations</span>
          </div>
          <p className="card-subtitle">
            Vertical scrolling timeline generating plain-English clinical notes on every visit.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          style={{ padding: "0.3rem 0.65rem", fontSize: "0.72rem" }}
          onClick={() => setReverseOrder(!reverseOrder)}
          title="Toggle timeline order"
        >
          <ArrowDownUp size={13} />
          {reverseOrder ? "Newest First" : "Oldest First"}
        </button>
      </div>

      {/* Latest Processed Note Banner */}
      {latestNote && (
        <div
          style={{
            margin: "0.75rem 0.75rem 0 0.75rem",
            padding: "0.65rem 0.85rem",
            background: "linear-gradient(135deg, var(--teal-light), #ffffff)",
            border: "1px solid var(--teal-border)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <Sparkles size={16} color="var(--teal-primary)" style={{ flexShrink: 0 }} />
          <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", lineHeight: 1.4 }}>
            <strong style={{ color: "var(--teal-primary)" }}>Just Recorded: </strong> {latestNote}
          </div>
        </div>
      )}

      {/* Vertical Scrolling Timeline Track */}
      <div
        className="timeline-track-container"
        style={{
          maxHeight: "420px",
          overflowY: "auto",
          padding: "1rem 0.75rem 0.5rem 0.75rem",
          display: "flex",
          flexDirection: "column",
          gap: "1.1rem",
          position: "relative",
        }}
      >
        {displayEntries.map((entry) => {
          const isBaselineVisit = entry.visit_number === 1;
          const deltaSign = entry.deltaFromPrev > 0 ? "+" : "";
          const isNegative = entry.deltaFromPrev < -0.01;
          const isPositive = entry.deltaFromPrev > 0.01;

          return (
            <div
              key={entry.visit_number}
              className="timeline-item"
              style={{
                display: "flex",
                gap: "0.85rem",
                position: "relative",
              }}
            >
              {/* Timeline Marker Node & Vertical Track */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  width: "28px",
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    width: "26px",
                    height: "26px",
                    borderRadius: "50%",
                    background: entry.hasExacerbation || entry.currentFEV1 <= 0.90
                      ? "var(--rose-light)"
                      : entry.isRapidDecliner
                      ? "var(--amber-light)"
                      : "var(--teal-light)",
                    border: `2px solid ${
                      entry.hasExacerbation || entry.currentFEV1 <= 0.90
                        ? "var(--rose-primary)"
                        : entry.isRapidDecliner
                        ? "var(--amber-primary)"
                        : "var(--teal-primary)"
                    }`,
                    color: entry.hasExacerbation || entry.currentFEV1 <= 0.90
                      ? "var(--rose-primary)"
                      : entry.isRapidDecliner
                      ? "var(--amber-primary)"
                      : "var(--teal-primary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.6875rem",
                    fontWeight: 800,
                    zIndex: 2,
                  }}
                >
                  {entry.visit_number}
                </div>
                <div
                  style={{
                    width: "2px",
                    flex: 1,
                    background: "var(--border-light)",
                    margin: "4px 0",
                    minHeight: "45px",
                  }}
                />
              </div>

              {/* Timeline Content Card with Plain-English Clinical Note */}
              <div
                style={{
                  flex: 1,
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-light)",
                  borderRadius: "var(--radius-md)",
                  padding: "0.85rem 1rem",
                  boxShadow: "var(--shadow-xs)",
                }}
              >
                {/* Header Row: Visit # & Timeline Metadata */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      Visit #{entry.visit_number}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Month {Number(entry.months_since_baseline).toFixed(1)} &bull; Age {entry.age_at_visit}y
                    </span>
                  </div>

                  {/* FEV1 Measurement & Delta */}
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ fontSize: "1rem", fontWeight: 800, color: "var(--text-primary)" }}>
                      {entry.currentFEV1.toFixed(3)} L
                    </span>

                    {!isBaselineVisit && (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          color: isNegative
                            ? "var(--rose-primary)"
                            : isPositive
                            ? "var(--emerald-primary)"
                            : "var(--text-muted)",
                          background: isNegative
                            ? "var(--rose-light)"
                            : isPositive
                            ? "var(--emerald-light)"
                            : "var(--bg-surface-secondary)",
                          padding: "0.15rem 0.45rem",
                          borderRadius: "4px",
                        }}
                      >
                        {isNegative ? (
                          <TrendingDown size={12} style={{ marginRight: "2px" }} />
                        ) : isPositive ? (
                          <TrendingUp size={12} style={{ marginRight: "2px" }} />
                        ) : (
                          <Minus size={12} style={{ marginRight: "2px" }} />
                        )}
                        {deltaSign}{entry.deltaFromPrev.toFixed(3)} L
                      </span>
                    )}
                  </div>
                </div>

                {/* Automated Plain-English Clinical Memory Note */}
                <div
                  style={{
                    marginTop: "0.6rem",
                    padding: "0.55rem 0.75rem",
                    borderRadius: "var(--radius-sm)",
                    background: entry.hasExacerbation || entry.currentFEV1 <= 0.90
                      ? "var(--rose-light)"
                      : entry.isRapidDecliner
                      ? "var(--amber-light)"
                      : "var(--bg-surface-secondary)",
                    borderLeft: `3px solid ${
                      entry.hasExacerbation || entry.currentFEV1 <= 0.90
                        ? "var(--rose-primary)"
                        : entry.isRapidDecliner
                        ? "var(--amber-primary)"
                        : "var(--teal-primary)"
                    }`,
                    display: "flex",
                    gap: "0.5rem",
                    alignItems: "flex-start",
                  }}
                >
                  <FileText size={14} color="var(--text-secondary)" style={{ marginTop: "2px", flexShrink: 0 }} />
                  <div style={{ fontSize: "0.78125rem", color: "var(--text-primary)", lineHeight: 1.45 }}>
                    <strong style={{ color: "var(--teal-primary)", fontWeight: 700 }}>Clinical Note: </strong>
                    {entry.clinicalNote}
                  </div>
                </div>

                {/* Risk Badges Row */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.65rem" }}>
                  {isBaselineVisit && (
                    <span className="badge" style={{ background: "var(--blue-light)", color: "var(--blue-primary)", borderColor: "var(--blue-border)", fontSize: "0.6875rem" }}>
                      Baseline Anchor
                    </span>
                  )}

                  {entry.hasExacerbation && (
                    <span
                      className="badge"
                      style={{
                        background: "var(--rose-light)",
                        color: "var(--rose-primary)",
                        borderColor: "var(--rose-border)",
                        fontSize: "0.6875rem",
                        fontWeight: 700,
                      }}
                    >
                      <AlertTriangle size={11} />
                      Exacerbation Alert ({entry.exacerbations_this_visit})
                    </span>
                  )}

                  {entry.isRapidDecliner && !isBaselineVisit && (
                    <span
                      className="badge"
                      style={{
                        background: "var(--amber-light)",
                        color: "var(--amber-primary)",
                        borderColor: "var(--amber-border)",
                        fontSize: "0.6875rem",
                      }}
                    >
                      Rapid Decliner
                    </span>
                  )}

                  <span
                    className="badge"
                    style={{
                      background: entry.isCurrentSmoker ? "var(--amber-light)" : "var(--emerald-light)",
                      color: entry.isCurrentSmoker ? "var(--amber-primary)" : "var(--emerald-primary)",
                      borderColor: entry.isCurrentSmoker ? "var(--amber-border)" : "var(--emerald-border)",
                      fontSize: "0.6875rem",
                      textTransform: "capitalize",
                    }}
                  >
                    {entry.smoking_status_at_visit === "former" ? "Cessation Maintained" : `${entry.smoking_status_at_visit} Smoker`}
                  </span>

                  <span
                    className="badge"
                    style={{
                      background: entry.isHighActivity ? "var(--emerald-light)" : "var(--bg-surface-secondary)",
                      color: entry.isHighActivity ? "var(--emerald-primary)" : "var(--text-secondary)",
                      fontSize: "0.6875rem",
                      textTransform: "capitalize",
                    }}
                  >
                    {entry.activity_level_at_visit} Activity
                  </span>

                  {entry.measurement_source && (
                    <span
                      className="badge"
                      style={{
                        background: "var(--bg-surface-secondary)",
                        color: "var(--text-muted)",
                        fontSize: "0.6875rem",
                      }}
                    >
                      <MapPin size={10} />
                      {entry.measurement_source}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
