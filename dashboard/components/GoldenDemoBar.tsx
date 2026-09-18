"use client";

import React from "react";
import { Zap, TrendingDown, ShieldCheck, Flame } from "lucide-react";
import { GOLDEN_PATIENTS, GoldenPatient } from "../lib/goldenPatients";

interface GoldenDemoBarProps {
  selectedPatientId: string;
  onSelectPatient: (patient: GoldenPatient) => void;
}

export default function GoldenDemoBar({
  selectedPatientId,
  onSelectPatient,
}: GoldenDemoBarProps) {
  const getIcon = (archetype: string) => {
    switch (archetype) {
      case "rapid_decliner":
        return <TrendingDown size={18} color="#e11d48" />;
      case "stable_maintenance":
        return <ShieldCheck size={18} color="#059669" />;
      case "intervention_sensitive":
        return <Flame size={18} color="#0d9488" />;
      default:
        return <Zap size={18} />;
    }
  };

  return (
    <section className="golden-bar-container" aria-label="Pre-seeded Golden Demo Patients">
      <div className="golden-bar-header">
        <div className="golden-bar-title">
          <Zap size={15} color="#0d9488" />
          <span>Golden Demo Profiles (Pre-seeded Archetypes)</span>
        </div>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          Select an archetype to auto-populate inputs across all three demo layers
        </span>
      </div>

      <div className="golden-badges-grid">
        {GOLDEN_PATIENTS.map((p) => {
          const isSelected = selectedPatientId === p.id;
          const activeClass = isSelected ? `active-${p.colorScheme}` : "";

          return (
            <button
              key={p.id}
              id={`golden-btn-${p.id}`}
              type="button"
              className={`golden-card ${activeClass}`}
              onClick={() => onSelectPatient(p)}
            >
              <div className="golden-top-row">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  {getIcon(p.archetype)}
                  <span className="golden-name">{p.name}</span>
                </div>
                <span
                  className="badge"
                  style={{
                    backgroundColor:
                      p.colorScheme === "rose"
                        ? "var(--rose-light)"
                        : p.colorScheme === "emerald"
                        ? "var(--emerald-light)"
                        : "var(--teal-light)",
                    color:
                      p.colorScheme === "rose"
                        ? "var(--rose-primary)"
                        : p.colorScheme === "emerald"
                        ? "var(--emerald-primary)"
                        : "var(--teal-primary)",
                    border: `1px solid ${
                      p.colorScheme === "rose"
                        ? "var(--rose-border)"
                        : p.colorScheme === "emerald"
                        ? "var(--emerald-border)"
                        : "var(--teal-border)"
                    }`,
                  }}
                >
                  {p.badgeLabel}
                </span>
              </div>

              <p className="golden-tagline">{p.tagline}</p>

              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  fontSize: "0.6875rem",
                  color: "var(--text-muted)",
                  marginTop: "0.25rem",
                }}
              >
                <span>{p.quickMetrics.sex}, {p.quickMetrics.age}y</span>
                <span>•</span>
                <span>{p.quickMetrics.goldStage}</span>
                <span>•</span>
                <span>FEV1 {p.quickMetrics.baselineFEV1}L</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
