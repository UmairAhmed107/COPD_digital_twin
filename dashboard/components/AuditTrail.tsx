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
}

interface AuditTrailProps {
  history: Array<AuditTrailEntry | Record<string, any>>;
  baselineFEV1?: number;
  patientId?: string;
}

export default function AuditTrail({
  history,
  baselineFEV1 = 2.0,
  patientId,
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

  // Calculate deltas sequentially
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
              Clinical Audit Timeline
            </h3>
            <span className="badge badge-demo">{history.length} Observations</span>
          </div>
          <p className="card-subtitle">
            Chronological log of clinical observations, FEV1 velocity, and clinical risk badges.
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

      {/* Vertical Timeline Track */}
      <div
        className="timeline-track-container"
        style={{
          maxHeight: "380px",
          overflowY: "auto",
          padding: "1rem 0.5rem 0.5rem 0.5rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
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
                gap: "1rem",
                position: "relative",
              }}
            >
              {/* Timeline Marker Line & Node */}
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
                    width: "24px",
                    height: "24px",
                    borderRadius: "50%",
                    background: entry.hasExacerbation
                      ? "var(--rose-light)"
                      : entry.isRapidDecliner
                      ? "var(--amber-light)"
                      : "var(--teal-light)",
                    border: `2px solid ${
                      entry.hasExacerbation
                        ? "var(--rose-primary)"
                        : entry.isRapidDecliner
                        ? "var(--amber-primary)"
                        : "var(--teal-primary)"
                    }`,
                    color: entry.hasExacerbation
                      ? "var(--rose-primary)"
                      : entry.isRapidDecliner
                      ? "var(--amber-primary)"
                      : "var(--teal-primary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.65rem",
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
                    minHeight: "40px",
                  }}
                />
              </div>

              {/* Timeline Content Card */}
              <div
                style={{
                  flex: 1,
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-light)",
                  borderRadius: "var(--radius-md)",
                  padding: "0.75rem 1rem",
                  boxShadow: "var(--shadow-xs)",
                }}
              >
                {/* Header Row: Visit # & Timeline */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary)" }}>
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

                {/* Risk Badges Row */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.5rem" }}>
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
