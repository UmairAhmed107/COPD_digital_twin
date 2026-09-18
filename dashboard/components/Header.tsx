"use client";

import React, { useEffect, useState } from "react";
import { Activity, Cpu, Stethoscope, Sparkles, AlertCircle, Code } from "lucide-react";
import { checkApiHealth } from "../lib/api";

interface HeaderProps {
  activeLayer: "predict" | "twin" | "simulate";
  setActiveLayer: (layer: "predict" | "twin" | "simulate") => void;
  devMode?: boolean;
  onToggleDevMode?: () => void;
}

export default function Header({
  activeLayer,
  setActiveLayer,
  devMode = false,
  onToggleDevMode,
}: HeaderProps) {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [loadedCount, setLoadedCount] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function checkHealth() {
      try {
        const res = await checkApiHealth();
        if (isMounted) {
          setIsOnline(res.status === "online");
          if (res.loaded_patients !== undefined) {
            setLoadedCount(res.loaded_patients);
          }
        }
      } catch {
        if (isMounted) {
          setIsOnline(false);
        }
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="header-wrapper">
      <div className="header-inner">
        <div className="brand-section">
          <div className="brand-icon">
            <Stethoscope size={22} />
          </div>
          <div>
            <h1 className="brand-title">
              COPD Digital Twin
              <span className="badge badge-demo">Academic Demo</span>
            </h1>
            <p className="brand-subtitle">
              Interactive State Tracking &amp; Machine Learning Trajectory Simulation
            </p>
          </div>
        </div>

        <div className="header-badges">
          {isOnline === true ? (
            <span className="badge badge-online" title="Connected to FastAPI backend on port 8000">
              <span className="status-dot"></span>
              API Online {loadedCount ? `(${loadedCount} twins)` : ""}
            </span>
          ) : isOnline === false ? (
            <span className="badge badge-offline" title="Ensure 'uvicorn api.main:app --port 8000' is running">
              <AlertCircle size={13} />
              API Offline (:8000)
            </span>
          ) : (
            <span className="badge badge-demo">Connecting...</span>
          )}

          {/* Dev Mode Switch */}
          <button
            id="toggle-dev-mode-btn"
            type="button"
            className="badge"
            style={{
              cursor: "pointer",
              padding: "0.35rem 0.75rem",
              border: devMode ? "1px solid var(--teal-primary)" : "1px solid var(--border-light)",
              background: devMode ? "var(--teal-light)" : "var(--bg-surface)",
              color: devMode ? "var(--teal-primary)" : "var(--text-secondary)",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.4rem",
              fontWeight: 600,
              fontSize: "0.75rem",
              borderRadius: "var(--radius-full)",
              transition: "all 0.15s ease",
            }}
            onClick={onToggleDevMode}
            title="Toggle live JSON twin state inspector"
          >
            <Code size={13} />
            <span>Dev Mode</span>
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                background: devMode ? "var(--teal-primary)" : "var(--border-hover)",
                display: "inline-block",
              }}
            />
          </button>

          <nav className="tab-nav" aria-label="Demo layers navigation">
            <button
              id="nav-layer-1"
              type="button"
              className={`tab-button ${activeLayer === "predict" ? "active" : ""}`}
              onClick={() => setActiveLayer("predict")}
            >
              <Cpu size={16} />
              Layer 1: Single Prediction
            </button>
            <button
              id="nav-layer-2"
              type="button"
              className={`tab-button ${activeLayer === "twin" ? "active" : ""}`}
              onClick={() => setActiveLayer("twin")}
            >
              <Activity size={16} />
              Layer 2: Evolving Twin
            </button>
            <button
              id="nav-layer-3"
              type="button"
              className={`tab-button ${activeLayer === "simulate" ? "active" : ""}`}
              onClick={() => setActiveLayer("simulate")}
            >
              <Sparkles size={16} />
              Layer 3: What-If Simulation
            </button>
          </nav>
        </div>
      </div>
    </header>
  );
}
