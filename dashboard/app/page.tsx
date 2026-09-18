"use client";

import React, { useState, useEffect } from "react";
import Header from "../components/Header";
import GoldenDemoBar from "../components/GoldenDemoBar";
import Layer1Prediction from "../components/Layer1Prediction";
import Layer2EvolvingTwin from "../components/Layer2EvolvingTwin";
import Layer3Simulation from "../components/Layer3Simulation";
import DataInspector from "../components/DataInspector";
import { GOLDEN_PATIENTS, GoldenPatient } from "../lib/goldenPatients";
import { getPatient } from "../lib/api";
import { TwinStateResponse } from "../lib/types";

export default function Home() {
  const [activeLayer, setActiveLayer] = useState<"predict" | "twin" | "simulate">("twin");
  const [selectedPatient, setSelectedPatient] = useState<GoldenPatient>(GOLDEN_PATIENTS[2]); // Default to P0001 (Intervention-Sensitive)
  const [devMode, setDevMode] = useState<boolean>(false);
  const [activeTwinState, setActiveTwinState] = useState<TwinStateResponse | null>(null);

  // Sync active twin state when selected patient changes
  useEffect(() => {
    let mounted = true;
    async function syncTwin() {
      try {
        const data = await getPatient(selectedPatient.id);
        if (mounted) setActiveTwinState(data);
      } catch {
        // Handled silently
      }
    }
    syncTwin();
    return () => {
      mounted = false;
    };
  }, [selectedPatient.id]);

  const handleSelectGoldenPatient = (p: GoldenPatient) => {
    setSelectedPatient(p);
  };

  const handleSelectPatientId = (id: string) => {
    const matched = GOLDEN_PATIENTS.find((p) => p.id === id);
    if (matched) {
      setSelectedPatient(matched);
    } else {
      setSelectedPatient({
        id,
        name: `Patient ${id}`,
        archetype: "stable_maintenance",
        badgeLabel: "Selected",
        colorScheme: "teal",
        tagline: "Custom patient loaded from digital twin cohort",
        clinicalNarrative: "Patient loaded from synthetic longitudinal dataset.",
        quickMetrics: {
          age: 65,
          sex: "M",
          goldStage: "II (Moderate)",
          smoking: "Former",
          packYears: 30,
          baselineFEV1: 2.0,
        },
        samplePredictValues: {
          age_at_visit: 65,
          sex: "M",
          gold_stage_baseline: "II (Moderate)",
          smoking_status_at_visit: "former",
          pack_years: 30,
          activity_level_at_visit: "moderate",
          bmi: 26,
          months_since_baseline: 12,
          baseline_fev1_liters: 2.0,
        },
      });
    }
  };

  const handleTwinStateChange = React.useCallback((ts: TwinStateResponse) => {
    setActiveTwinState(ts);
  }, []);

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Header
        activeLayer={activeLayer}
        setActiveLayer={setActiveLayer}
        devMode={devMode}
        onToggleDevMode={() => setDevMode(!devMode)}
      />

      <main className="app-container" style={{ flex: 1 }}>
        {/* Persistent Quick-Select Golden Demo Bar */}
        <GoldenDemoBar
          selectedPatientId={selectedPatient.id}
          onSelectPatient={handleSelectGoldenPatient}
        />

        {/* Dynamic Layer Switcher */}
        {activeLayer === "predict" && (
          <Layer1Prediction
            initialValues={selectedPatient.samplePredictValues}
            activeGoldenPatient={selectedPatient}
          />
        )}

        {activeLayer === "twin" && (
          <Layer2EvolvingTwin
            selectedPatientId={selectedPatient.id}
            onSelectPatientId={handleSelectPatientId}
            onTwinStateChange={handleTwinStateChange}
          />
        )}

        {activeLayer === "simulate" && (
          <Layer3Simulation selectedPatientId={selectedPatient.id} />
        )}
      </main>

      {/* Floating Under-the-Hood Data Inspector Drawer */}
      <DataInspector
        isOpen={devMode}
        onClose={() => setDevMode(false)}
        twinState={activeTwinState}
        activePatientId={selectedPatient.id}
      />

      {/* Medical Disclaimer Footer */}
      <footer
        style={{
          borderTop: "1px solid var(--border-light)",
          background: "var(--bg-surface)",
          padding: "1.25rem 1.5rem",
          fontSize: "0.75rem",
          color: "var(--text-secondary)",
          textAlign: "center",
          marginTop: "2rem",
        }}
      >
        <div style={{ maxWidth: "1280px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
          <span>
            <strong>COPD Digital Twin v2</strong> — Educational Machine Learning &amp; Simulation Demonstration
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            Academic Course Demo — Not intended for real clinical medical treatment decisions
          </span>
        </div>
      </footer>
    </div>
  );
}

