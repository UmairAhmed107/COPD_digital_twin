import { PredictRequest } from "./types";

export interface GoldenPatient {
  id: string;
  name: string;
  archetype: "rapid_decliner" | "stable_maintenance" | "intervention_sensitive";
  badgeLabel: string;
  colorScheme: "rose" | "emerald" | "teal";
  tagline: string;
  clinicalNarrative: string;
  quickMetrics: {
    age: number;
    sex: string;
    goldStage: string;
    smoking: string;
    packYears: number;
    baselineFEV1: number;
  };
  samplePredictValues: PredictRequest;
}

export const GOLDEN_PATIENTS: GoldenPatient[] = [
  {
    id: "P0124",
    name: "Patient P0124",
    archetype: "rapid_decliner",
    badgeLabel: "Rapid Decliner",
    colorScheme: "rose",
    tagline: "Heavy active smoker with accelerated lung function decay",
    clinicalNarrative:
      "Male, 66 years old, 44.4 pack-years with continuous smoking. Baseline FEV1 of 1.58L has precipitously fallen to 1.13L over 64 months. Represents advanced COPD with high exacerbation risk.",
    quickMetrics: {
      age: 66,
      sex: "M",
      goldStage: "IV (Very Severe)",
      smoking: "Current",
      packYears: 44.4,
      baselineFEV1: 1.58,
    },
    samplePredictValues: {
      age_at_visit: 68.0,
      sex: "M",
      gold_stage_baseline: "IV (Very Severe)",
      smoking_status_at_visit: "current",
      pack_years: 45.0,
      activity_level_at_visit: "low",
      bmi: 23.8,
      months_since_baseline: 24.0,
      baseline_fev1_liters: 1.58,
    },
  },
  {
    id: "P0040",
    name: "Patient P0040",
    archetype: "stable_maintenance",
    badgeLabel: "Stable Maintenance",
    colorScheme: "emerald",
    tagline: "Former smoker maintaining high physical activity and preserved FEV1",
    clinicalNarrative:
      "Female, 62 years old, former smoker with moderate baseline pack-years (33.8). Adheres to high physical activity; FEV1 has remained virtually preserved around 1.65L across 8 clinic visits over 4+ years.",
    quickMetrics: {
      age: 62,
      sex: "F",
      goldStage: "II (Moderate)",
      smoking: "Former",
      packYears: 33.8,
      baselineFEV1: 1.67,
    },
    samplePredictValues: {
      age_at_visit: 64.0,
      sex: "F",
      gold_stage_baseline: "II (Moderate)",
      smoking_status_at_visit: "former",
      pack_years: 33.8,
      activity_level_at_visit: "high",
      bmi: 27.2,
      months_since_baseline: 24.0,
      baseline_fev1_liters: 1.67,
    },
  },
  {
    id: "P0001",
    name: "Patient P0001",
    archetype: "intervention_sensitive",
    badgeLabel: "Intervention-Sensitive",
    colorScheme: "teal",
    tagline: "High-reversibility profile exhibiting strong gain from smoking cessation",
    clinicalNarrative:
      "Male, 65 years old, 45.2 pack-years, currently smoking. High baseline FEV1 (3.12L) beginning to decline. Future simulations reveal dramatic divergence (+0.28L preserved) when cessation and exercise are applied.",
    quickMetrics: {
      age: 65,
      sex: "M",
      goldStage: "II (Moderate)",
      smoking: "Current",
      packYears: 45.2,
      baselineFEV1: 3.12,
    },
    samplePredictValues: {
      age_at_visit: 67.0,
      sex: "M",
      gold_stage_baseline: "II (Moderate)",
      smoking_status_at_visit: "current",
      pack_years: 46.0,
      activity_level_at_visit: "moderate",
      bmi: 26.5,
      months_since_baseline: 24.0,
      baseline_fev1_liters: 3.12,
    },
  },
];
