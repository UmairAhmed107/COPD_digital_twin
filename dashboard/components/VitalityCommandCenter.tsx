"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  Clock,
  TrendingDown,
  Award,
  AlertTriangle,
  CheckCircle2,
  Users,
  ShieldAlert,
  Flame,
  Gauge,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { getTwinHealthScore, getCohortPercentile } from "../lib/api";
import { TwinHealthScoreResponse, CohortPercentileResponse } from "../lib/types";

interface VitalityCommandCenterProps {
  patientId: string;
  refreshKey?: number; // Optional prop to force reload when a new visit is appended
}

export default function VitalityCommandCenter({
  patientId,
  refreshKey = 0,
}: VitalityCommandCenterProps) {
  const [healthScore, setHealthScore] = useState<TwinHealthScoreResponse | null>(null);
  const [cohortRank, setCohortRank] = useState<CohortPercentileResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [animatedScore, setAnimatedScore] = useState<number>(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    async function fetchData() {
      try {
        const [scoreData, cohortData] = await Promise.all([
          getTwinHealthScore(patientId),
          getCohortPercentile(patientId),
        ]);
        if (mounted) {
          setHealthScore(scoreData);
          setCohortRank(cohortData);
        }
      } catch (err: any) {
        if (mounted) {
          setError(err.message || "Failed to load vitality command center data.");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    fetchData();

    return () => {
      mounted = false;
    };
  }, [patientId, refreshKey]);

  // Fluid spin-up animation for Health Score Gauge on mount and when score changes
  useEffect(() => {
    if (!healthScore) {
      setAnimatedScore(0);
      return;
    }

    const targetScore = Math.round(healthScore.health_score);
    const duration = 1000; // 1 second fluid spin-up
    const startTime = performance.now();
    let animId: number;

    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Cubic ease-out: 1 - (1 - progress)^3
      const ease = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(Math.round(ease * targetScore));

      if (progress < 1) {
        animId = requestAnimationFrame(step);
      }
    };

    animId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animId);
  }, [healthScore?.health_score, patientId]);

  if (loading) {
    return (
      <div
        className="card"
        style={{
          padding: "1.5rem",
          background: "linear-gradient(135deg, #0f172a, #1e293b)",
          color: "white",
          borderRadius: "var(--radius-lg)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "140px",
          boxShadow: "0 10px 25px -5px rgba(15, 23, 42, 0.4)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "#94a3b8" }}>
          <Activity size={20} className="animate-spin" />
          <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>
            Analyzing Vitality Metrics &amp; Population Cohort...
          </span>
        </div>
      </div>
    );
  }

  if (error || !healthScore) {
    return null; // Gracefully degrade if offline
  }

  // Determine color accents based on score_color
  const isGreen = healthScore.score_color === "green";
  const isAmber = healthScore.score_color === "amber";

  const accentColor = isGreen ? "#10b981" : isAmber ? "#f59e0b" : "#ef4444";
  const accentGlow = isGreen
    ? "rgba(16, 185, 129, 0.25)"
    : isAmber
    ? "rgba(245, 158, 11, 0.25)"
    : "rgba(239, 68, 68, 0.25)";

  const strokeDash = `${animatedScore * 2.512}, 251.2`;

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case "A":
        return { bg: "rgba(16, 185, 129, 0.15)", text: "#34d399", border: "rgba(16, 185, 129, 0.4)" };
      case "B":
        return { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa", border: "rgba(59, 130, 246, 0.4)" };
      case "C":
        return { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24", border: "rgba(245, 158, 11, 0.4)" };
      case "D":
        return { bg: "rgba(249, 115, 22, 0.15)", text: "#fb923c", border: "rgba(249, 115, 22, 0.4)" };
      default:
        return { bg: "rgba(239, 68, 68, 0.15)", text: "#f87171", border: "rgba(239, 68, 68, 0.4)" };
    }
  };

  return (
    <div
      style={{
        background: "linear-gradient(135deg, #0b1329 0%, #111e38 50%, #0f172a 100%)",
        borderRadius: "var(--radius-lg)",
        color: "#f8fafc",
        padding: "1.5rem",
        boxShadow: "0 10px 30px -5px rgba(11, 19, 41, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08)",
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background Decorative Ambient Radial Gradient */}
      <div
        style={{
          position: "absolute",
          top: "-30%",
          right: "-10%",
          width: "350px",
          height: "350px",
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accentGlow} 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      {/* Top Title & Header Tag */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <div
            style={{
              background: "rgba(255, 255, 255, 0.1)",
              borderRadius: "6px",
              padding: "0.35rem 0.6rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              fontSize: "0.75rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#38bdf8",
              border: "1px solid rgba(56, 189, 248, 0.3)",
            }}
          >
            <Gauge size={14} /> Vitality Command Center
          </div>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Patient <strong>{patientId}</strong> Continuous Biometric &amp; Cohort Telemetry
          </span>
        </div>

        {cohortRank && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.3rem 0.75rem",
              borderRadius: "var(--radius-full)",
              background: cohortRank.percentile < 30 ? "rgba(239, 68, 68, 0.2)" : cohortRank.percentile < 60 ? "rgba(245, 158, 11, 0.2)" : "rgba(16, 185, 129, 0.2)",
              border: `1px solid ${cohortRank.percentile < 30 ? "#ef4444" : cohortRank.percentile < 60 ? "#f59e0b" : "#10b981"}`,
              color: cohortRank.percentile < 30 ? "#fca5a5" : cohortRank.percentile < 60 ? "#fde68a" : "#6ee7b7",
              fontSize: "0.75rem",
              fontWeight: 700,
            }}
          >
            <Users size={13} />
            <span>{cohortRank.placement_banner}</span>
            <span style={{ opacity: 0.7, fontWeight: 400 }}>
              (Rank #{cohortRank.rank} / {cohortRank.cohort_size})
            </span>
          </div>
        )}
      </div>

      {/* High-Contrast Metrics Row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "1.25rem",
          alignItems: "stretch",
        }}
      >
        {/* Metric 1: Twin Health Score (0-100 Gauge) */}
        <div
          style={{
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "var(--radius-md)",
            padding: "1.25rem",
            display: "flex",
            alignItems: "center",
            gap: "1.25rem",
          }}
        >
          {/* Radial SVG Gauge */}
          <div style={{ position: "relative", width: "90px", height: "90px", flexShrink: 0 }}>
            <svg
              viewBox="0 0 100 100"
              style={{
                transform: "rotate(-90deg)",
                width: "100%",
                height: "100%",
                filter: `drop-shadow(0 0 8px ${accentGlow})`,
              }}
            >
              {/* Background track circle */}
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="transparent"
                stroke="rgba(255, 255, 255, 0.12)"
                strokeWidth="8"
              />
              {/* Value circle */}
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="transparent"
                stroke={accentColor}
                strokeWidth="8"
                strokeDasharray={strokeDash}
                strokeLinecap="round"
                style={{
                  transition: "stroke-dasharray 0.08s linear, stroke 0.4s ease",
                }}
              />
            </svg>
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span style={{ fontSize: "1.5rem", fontWeight: 800, color: "#ffffff", lineHeight: 1 }}>
                {animatedScore}
              </span>
              <span style={{ fontSize: "0.625rem", color: "#94a3b8", textTransform: "uppercase", marginTop: "2px" }}>
                Score
              </span>
            </div>
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase" }}>
              Twin Health Score
            </div>
            <div style={{ fontSize: "1.05rem", fontWeight: 700, color: accentColor, marginTop: "0.25rem" }}>
              {healthScore.status_label}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#cbd5e1", marginTop: "0.35rem" }}>
              Current: <strong>{healthScore.current_fev1.toFixed(2)}L</strong> FEV1 ({healthScore.exacerbation_risk_pct.toFixed(0)}% acute exac. risk)
            </div>
          </div>
        </div>

        {/* Metric 2: Ticking "Years until GOLD Stage IV" Countdown */}
        <div
          style={{
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "var(--radius-md)",
            padding: "1.25rem",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase" }}>
              GOLD Stage IV Countdown
            </span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
                fontSize: "0.7rem",
                color: "#fca5a5",
                background: "rgba(239, 68, 68, 0.15)",
                padding: "0.15rem 0.45rem",
                borderRadius: "4px",
              }}
            >
              <Clock size={12} /> Milestone
            </span>
          </div>

          <div style={{ margin: "0.4rem 0" }}>
            <div
              style={{
                fontSize: "1.85rem",
                fontWeight: 800,
                color: healthScore.years_until_gold_iv !== null && healthScore.years_until_gold_iv < 5 ? "#ef4444" : healthScore.years_until_gold_iv !== null && healthScore.years_until_gold_iv < 10 ? "#f59e0b" : "#38bdf8",
                letterSpacing: "-0.02em",
                lineHeight: 1.1,
              }}
            >
              {healthScore.years_until_gold_iv_display}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>
              Trajectory to critical threshold (&lt;0.90L) at current decline rate (-{healthScore.annual_decline_rate_ml} mL/yr).
            </div>
          </div>
        </div>

        {/* Metric 3: Report-Card Grades (A-F) */}
        <div
          style={{
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "var(--radius-md)",
            padding: "1.25rem",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase" }}>
              Report-Card Clinical Grades
            </span>
            <Award size={14} style={{ color: "#38bdf8" }} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
            {/* Grade 1: Lung Function */}
            {(() => {
              const g = healthScore.grades.lung_function || "C";
              const c = getGradeColor(g);
              return (
                <div
                  style={{
                    background: c.bg,
                    border: `1px solid ${c.border}`,
                    borderRadius: "6px",
                    padding: "0.5rem",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "1.25rem", fontWeight: 800, color: c.text }}>{g}</div>
                  <div style={{ fontSize: "0.625rem", color: "#cbd5e1", marginTop: "2px" }}>Lung Function</div>
                </div>
              );
            })()}

            {/* Grade 2: Decline Rate */}
            {(() => {
              const g = healthScore.grades.decline_rate || "C";
              const c = getGradeColor(g);
              return (
                <div
                  style={{
                    background: c.bg,
                    border: `1px solid ${c.border}`,
                    borderRadius: "6px",
                    padding: "0.5rem",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "1.25rem", fontWeight: 800, color: c.text }}>{g}</div>
                  <div style={{ fontSize: "0.625rem", color: "#cbd5e1", marginTop: "2px" }}>Decline Rate</div>
                </div>
              );
            })()}

            {/* Grade 3: Risk Trend */}
            {(() => {
              const g = healthScore.grades.risk_trend || "B";
              const c = getGradeColor(g);
              return (
                <div
                  style={{
                    background: c.bg,
                    border: `1px solid ${c.border}`,
                    borderRadius: "6px",
                    padding: "0.5rem",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "1.25rem", fontWeight: 800, color: c.text }}>{g}</div>
                  <div style={{ fontSize: "0.625rem", color: "#cbd5e1", marginTop: "2px" }}>Risk Trend</div>
                </div>
              );
            })()}
          </div>

          <div style={{ fontSize: "0.7rem", color: "#94a3b8", marginTop: "0.5rem" }}>
            Benchmarked against longitudinal GOLD COPD staging criteria.
          </div>
        </div>
      </div>
    </div>
  );
}
