"use client";

import React, { useId } from "react";
import { Activity, Info } from "lucide-react";

interface LungVisualizerProps {
  fev1: number;
  goldStage?: string;
  baselineFev1?: number;
  referenceCapacity?: number;
  title?: string;
  subtitle?: string;
  size?: "sm" | "md" | "lg";
  showStats?: boolean;
}

interface GoldColorConfig {
  primary: string;
  light: string;
  border: string;
  glow: string;
  label: string;
  stageName: string;
}

export function getGoldColorConfig(goldStageStr: string = "II"): GoldColorConfig {
  const norm = goldStageStr.toUpperCase();
  if (norm.includes("IV") || norm.includes("4") || norm.includes("VERY SEVERE")) {
    return {
      primary: "var(--rose-primary)",
      light: "var(--rose-light)",
      border: "var(--rose-border)",
      glow: "rgba(225, 29, 72, 0.35)",
      label: "Stage IV",
      stageName: "Very Severe Obstruction",
    };
  }
  if (norm.includes("III") || norm.includes("3") || norm.includes("SEVERE")) {
    return {
      primary: "var(--amber-primary)",
      light: "var(--amber-light)",
      border: "var(--amber-border)",
      glow: "rgba(217, 119, 6, 0.35)",
      label: "Stage III",
      stageName: "Severe Obstruction",
    };
  }
  if (norm.includes("II") || norm.includes("2") || norm.includes("MODERATE")) {
    return {
      primary: "var(--teal-primary)",
      light: "var(--teal-light)",
      border: "var(--teal-border)",
      glow: "rgba(13, 148, 136, 0.35)",
      label: "Stage II",
      stageName: "Moderate Obstruction",
    };
  }
  return {
    primary: "var(--emerald-primary)",
    light: "var(--emerald-light)",
    border: "var(--emerald-border)",
    glow: "rgba(5, 150, 105, 0.35)",
    label: "Stage I",
    stageName: "Mild Obstruction",
  };
}

export default function LungVisualizer({
  fev1,
  goldStage = "II",
  baselineFev1,
  referenceCapacity = 3.5,
  title = "Lung Capacity Gauge",
  subtitle = "Current spirometric capacity",
  size = "md",
  showStats = true,
}: LungVisualizerProps) {
  const uniqueId = useId().replace(/:/g, "");
  const colorCfg = getGoldColorConfig(goldStage);

  // Clamp fill percentage between 10% and 100%
  const percentage = Math.min(100, Math.max(10, Math.round((fev1 / referenceCapacity) * 100)));
  
  // In SVG coordinates (viewBox 0 0 200 210), lungs vertical span is roughly y=45 to y=195 (height 150)
  const lungTopY = 45;
  const lungBottomY = 195;
  const totalHeight = lungBottomY - lungTopY;
  const fillHeight = (percentage / 100) * totalHeight;
  const rectY = lungBottomY - fillHeight;

  // Size dimensions
  const dimensions = {
    sm: { width: 140, height: 155 },
    md: { width: 190, height: 210 },
    lg: { width: 240, height: 265 },
  }[size];

  // Anatomical paths
  // Right lung (on viewer's left side): X roughly 30..92, Y 48..192
  const rightLungPath =
    "M 88,52 C 82,46 68,48 58,58 C 42,74 32,102 32,132 C 32,160 40,188 56,192 C 68,194 82,185 88,172 C 92,160 90,120 90,95 C 90,75 92,58 88,52 Z";

  // Left lung (on viewer's right side, with cardiac notch): X roughly 108..168, Y 48..192
  const leftLungPath =
    "M 112,52 C 118,46 132,48 142,58 C 158,74 168,102 168,132 C 168,160 160,188 144,192 C 132,194 122,185 116,168 C 110,152 110,140 106,128 C 104,112 110,95 110,75 C 110,60 108,55 112,52 Z";

  return (
    <div className="lung-visualizer-wrapper" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      {/* Title & Badge */}
      <div style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <div>
          <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--text-muted)" }}>
            {title}
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
            {subtitle}
          </div>
        </div>
        <span
          className="badge"
          style={{
            background: colorCfg.light,
            color: colorCfg.primary,
            borderColor: colorCfg.border,
            fontSize: "0.7rem",
            fontWeight: 700,
          }}
        >
          {colorCfg.label}
        </span>
      </div>

      {/* SVG Container with subtle ambient glow */}
      <div
        className="lung-svg-container"
        style={{
          position: "relative",
          width: dimensions.width,
          height: dimensions.height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <svg
          viewBox="0 0 200 210"
          width={dimensions.width}
          height={dimensions.height}
          style={{ overflow: "visible" }}
          role="img"
          aria-label={`Lung visualizer showing ${percentage}% capacity (${fev1.toFixed(2)}L), ${colorCfg.stageName}`}
        >
          <defs>
            {/* Combined Lung Silhouette Clip Path */}
            <clipPath id={`lung-clip-${uniqueId}`}>
              <path d={rightLungPath} />
              <path d={leftLungPath} />
            </clipPath>

            {/* Stage Gradient for Liquid Fill */}
            <linearGradient id={`lung-grad-${uniqueId}`} x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor={colorCfg.primary} stopOpacity="0.95" />
              <stop offset="70%" stopColor={colorCfg.primary} stopOpacity="0.75" />
              <stop offset="100%" stopColor={colorCfg.primary} stopOpacity="0.5" />
            </linearGradient>

            {/* Background Empty Lung Gradient */}
            <linearGradient id={`lung-empty-grad-${uniqueId}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f1f5f9" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#e2e8f0" stopOpacity="0.7" />
            </linearGradient>

            {/* Filter Glow Effect */}
            <filter id={`ambient-glow-${uniqueId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor={colorCfg.primary} floodOpacity="0.28" />
            </filter>
          </defs>

          {/* Ambient Glow Background Layer */}
          <g filter={`url(#ambient-glow-${uniqueId})`}>
            <path d={rightLungPath} fill="none" stroke={colorCfg.primary} strokeWidth="1.5" strokeOpacity="0.3" />
            <path d={leftLungPath} fill="none" stroke={colorCfg.primary} strokeWidth="1.5" strokeOpacity="0.3" />
          </g>

          {/* Trachea & Mainstem Bronchi (Anatomical Anchor) */}
          <g opacity="0.65">
            {/* Trachea */}
            <path
              d="M 96,12 L 104,12 L 104,45 C 104,47 101,49 100,50 C 99,49 96,47 96,45 Z"
              fill="#cbd5e1"
              stroke="#94a3b8"
              strokeWidth="1.2"
            />
            {/* Tracheal rings */}
            <line x1="96" y1="18" x2="104" y2="18" stroke="#94a3b8" strokeWidth="1" />
            <line x1="96" y1="25" x2="104" y2="25" stroke="#94a3b8" strokeWidth="1" />
            <line x1="96" y1="32" x2="104" y2="32" stroke="#94a3b8" strokeWidth="1" />
            <line x1="96" y1="39" x2="104" y2="39" stroke="#94a3b8" strokeWidth="1" />

            {/* Right bronchus */}
            <path d="M 97,47 Q 85,58 75,70" fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M 78,64 Q 68,76 62,88" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round" />

            {/* Left bronchus */}
            <path d="M 103,47 Q 115,58 125,70" fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M 122,64 Q 132,76 138,88" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round" />
          </g>

          {/* Base Empty Silhouette (Unfilled Capacity) */}
          <g>
            <path d={rightLungPath} fill={`url(#lung-empty-grad-${uniqueId})`} stroke="#cbd5e1" strokeWidth="1.5" />
            <path d={leftLungPath} fill={`url(#lung-empty-grad-${uniqueId})`} stroke="#cbd5e1" strokeWidth="1.5" />
          </g>

          {/* Clipped Liquid Fill Layer */}
          <g clipPath={`url(#lung-clip-${uniqueId})`}>
            {/* Filled Volume Rect */}
            <rect
              x="20"
              y={rectY}
              width="160"
              height={fillHeight + 20}
              fill={`url(#lung-grad-${uniqueId})`}
              style={{ transition: "all 0.6s cubic-bezier(0.16, 1, 0.3, 1)" }}
            />

            {/* Fluid Meniscus/Surface Highlight Line */}
            <line
              x1="20"
              y1={rectY}
              x2="180"
              y2={rectY}
              stroke="white"
              strokeWidth="2"
              strokeOpacity="0.6"
              style={{ transition: "all 0.6s cubic-bezier(0.16, 1, 0.3, 1)" }}
            />

            {/* Internal Rib Impression lines */}
            <g opacity="0.15" stroke="white" strokeWidth="1.5">
              <line x1="45" y1="90" x2="80" y2="95" />
              <line x1="40" y1="120" x2="82" y2="125" />
              <line x1="45" y1="150" x2="80" y2="155" />
              <line x1="120" y1="95" x2="155" y2="90" />
              <line x1="118" y1="125" x2="160" y2="120" />
              <line x1="120" y1="155" x2="155" y2="150" />
            </g>
          </g>

          {/* External Outline & Border */}
          <path d={rightLungPath} fill="none" stroke={colorCfg.primary} strokeWidth="1.6" strokeOpacity="0.8" />
          <path d={leftLungPath} fill="none" stroke={colorCfg.primary} strokeWidth="1.6" strokeOpacity="0.8" />

          {/* Center Fill Percentage Display */}
          <text
            x="100"
            y="135"
            textAnchor="middle"
            fill="var(--text-primary)"
            fontSize={size === "sm" ? "14" : "18"}
            fontWeight="800"
            style={{ pointerEvents: "none", textShadow: "0 1px 3px rgba(255,255,255,0.9)" }}
          >
            {percentage}%
          </text>
          <text
            x="100"
            y="149"
            textAnchor="middle"
            fill="var(--text-secondary)"
            fontSize={size === "sm" ? "8" : "10"}
            fontWeight="600"
            style={{ pointerEvents: "none" }}
          >
            CAPACITY
          </text>
        </svg>
      </div>

      {/* Stats Below */}
      {showStats && (
        <div style={{ width: "100%", marginTop: "0.5rem", textAlign: "center" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: "0.3rem" }}>
            <span style={{ fontSize: "1.25rem", fontWeight: 800, color: colorCfg.primary }}>
              {fev1.toFixed(2)}
            </span>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
              / {referenceCapacity.toFixed(1)} L Ref
            </span>
          </div>

          {baselineFev1 && baselineFev1 !== fev1 && (
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.1rem" }}>
              Baseline: {baselineFev1.toFixed(2)} L (
              <span style={{ color: fev1 >= baselineFev1 ? "var(--emerald-primary)" : "var(--rose-primary)", fontWeight: 600 }}>
                {fev1 >= baselineFev1 ? "+" : ""}
                {(fev1 - baselineFev1).toFixed(2)} L
              </span>
              )
            </div>
          )}

          {/* Medical Disclaimer Note */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.25rem",
              fontSize: "0.65rem",
              color: "var(--text-muted)",
              marginTop: "0.35rem",
              background: "var(--bg-surface-secondary)",
              padding: "0.15rem 0.5rem",
              borderRadius: "var(--radius-full)",
            }}
          >
            <Info size={10} />
            Illustrative Physiological Gauge
          </div>
        </div>
      )}
    </div>
  );
}
