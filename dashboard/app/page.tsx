"use client";

import React, { useState, useEffect } from "react";
import Header from "../components/Header";
import GoldenDemoBar from "../components/GoldenDemoBar";
import Layer1Prediction from "../components/Layer1Prediction";
import Layer2EvolvingTwin from "../components/Layer2EvolvingTwin";
import Layer3Simulation from "../components/Layer3Simulation";
import DataInspector from "../components/DataInspector";
import CreateTwinModal from "../components/CreateTwinModal";
import { GOLDEN_PATIENTS, GoldenPatient } from "../lib/goldenPatients";
import { getPatient } from "../lib/api";
import { PredictRequest, TwinStateResponse } from "../lib/types";

export default function Home() {
  const [activeLayer, setActiveLayer] = useState<"predict" | "twin" | "simulate">("twin");
  const [selectedPatient, setSelectedPatient] = useState<GoldenPatient>(GOLDEN_PATIENTS[2]); // Default to P0001 (Intervention-Sensitive)
  const [devMode, setDevMode] = useState<boolean>(false);
  const [activeTwinState, setActiveTwinState] = useState<TwinStateResponse | null>(null);
  const [patientVitals, setPatientVitals] = useState<PredictRequest | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);

  // Sync active twin state and extract real-world vitals when selected patient changes
  useEffect(() => {
    let mounted = true;
    async function syncTwin() {
      try {
        const data = await getPatient(selectedPatient.id);
        if (mounted) {
          setActiveTwinState(data);

          // Extract latest real-world vitals from the patient's twin state
          const latestVisit =
            data.history && data.history.length > 0
              ? data.history[data.history.length - 1]
              : data.current || {};

          const extractedVitals: PredictRequest = {
            age_at_visit: Number(latestVisit.age_at_visit ?? data.static?.age_at_baseline ?? 65),
            sex: String(data.static?.sex ?? "M"),
            gold_stage_baseline: String(data.static?.gold_stage_baseline ?? "II (Moderate)"),
            smoking_status_at_visit: String(
              latestVisit.smoking_status_at_visit ?? data.static?.smoking_status_baseline ?? "former"
            ),
            pack_years: Number(data.static?.pack_years ?? 30),
            activity_level_at_visit: String(latestVisit.activity_level_at_visit ?? "moderate"),
            bmi: Number(data.static?.bmi ?? 26),
            months_since_baseline: Number(latestVisit.months_since_baseline ?? 0),
            baseline_fev1_liters: Number(
              data.static?.baseline_fev1_liters ?? latestVisit.fev1_liters ?? 2.0
            ),
          };

          setPatientVitals(extractedVitals);
        }
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
    setPatientVitals(p.samplePredictValues);
  };

  const handleSelectPatientId = (id: string) => {
    const matched = GOLDEN_PATIENTS.find((p) => p.id === id);
    if (matched) {
      setSelectedPatient(matched);
      setPatientVitals(matched.samplePredictValues);
    } else {
      setSelectedPatient({
        id,
        name: `Patient ${id}`,
        archetype: "stable_maintenance",
        badgeLabel: "Cohort Twin",
        colorScheme: "teal",
        tagline: "Cohort digital twin loaded from database",
        clinicalNarrative: `Inspecting digital twin record for patient ${id}.`,
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

  const handlePatientCreated = (newTwin: TwinStateResponse) => {
    handleSelectPatientId(newTwin.patient_id);
    setActiveTwinState(newTwin);
    setActiveLayer("twin");
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Header
        activeLayer={activeLayer}
        setActiveLayer={setActiveLayer}
        devMode={devMode}
        onToggleDevMode={() => setDevMode(!devMode)}
        onOpenCreateModal={() => setIsCreateModalOpen(true)}
        selectedPatientId={selectedPatient.id}
        onSelectPatientId={handleSelectPatientId}
      />

      <main className="app-container" style={{ flex: 1 }}>
        {/* Persistent Quick-Select Golden Demo Bar with Integrated Search */}
        <GoldenDemoBar
          selectedPatientId={selectedPatient.id}
          onSelectPatient={handleSelectGoldenPatient}
          onSelectPatientId={handleSelectPatientId}
        />

        {/* Dynamic Layer Switcher */}
        {activeLayer === "predict" && (
          <Layer1Prediction
            key={selectedPatient.id}
            initialValues={patientVitals || selectedPatient.samplePredictValues}
            activeGoldenPatient={selectedPatient}
            selectedPatientId={selectedPatient.id}
            onSelectPatientId={handleSelectPatientId}
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
          <Layer3Simulation
            selectedPatientId={selectedPatient.id}
            onSelectPatientId={handleSelectPatientId}
          />
        )}
      </main>

      {/* Floating Under-the-Hood Data Inspector Drawer */}
      <DataInspector
        isOpen={devMode}
        onClose={() => setDevMode(false)}
        twinState={activeTwinState}
        activePatientId={selectedPatient.id}
      />

      {/* Global Create Digital Twin Onboarding Modal */}
      <CreateTwinModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={handlePatientCreated}
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

