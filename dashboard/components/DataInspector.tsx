"use client";

import React, { useState, useMemo } from "react";
import {
  Code,
  Copy,
  Check,
  X,
  Database,
  Search,
  Maximize2,
  Minimize2,
  FileJson,
  Layers,
} from "lucide-react";
import { TwinStateResponse } from "../lib/types";

interface DataInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  twinState: TwinStateResponse | null;
  activePatientId: string;
}

type TabType = "all" | "static" | "current" | "history";

export default function DataInspector({
  isOpen,
  onClose,
  twinState,
  activePatientId,
}: DataInspectorProps) {
  const [activeTab, setActiveTab] = useState<TabType>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);
  const [expanded, setExpanded] = useState<boolean>(false);

  // Selected JSON slice based on tab
  const displayData = useMemo(() => {
    if (!twinState) return null;
    switch (activeTab) {
      case "static":
        return twinState.static;
      case "current":
        return twinState.current;
      case "history":
        return twinState.history;
      case "all":
      default:
        return twinState;
    }
  }, [twinState, activeTab]);

  const jsonString = useMemo(() => {
    if (!displayData) return "{\n  \"message\": \"No digital twin loaded\"\n}";
    return JSON.stringify(displayData, null, 2);
  }, [displayData]);

  // Filtered JSON text if searching
  const filteredJsonString = useMemo(() => {
    if (!searchQuery.trim()) return jsonString;
    const lines = jsonString.split("\n");
    return lines
      .filter((line) => line.toLowerCase().includes(searchQuery.toLowerCase()))
      .join("\n");
  }, [jsonString, searchQuery]);

  const handleCopy = () => {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div
      className="data-inspector-container"
      style={{
        position: "fixed",
        right: 0,
        bottom: 0,
        top: 0,
        width: expanded ? "780px" : "500px",
        maxWidth: "95vw",
        background: "#0f172a",
        color: "#f8fafc",
        borderLeft: "1px solid #334155",
        boxShadow: "-10px 0 30px rgba(0, 0, 0, 0.35)",
        zIndex: 110,
        display: "flex",
        flexDirection: "column",
        transition: "width 0.25s ease",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      }}
      role="dialog"
      aria-label="Digital Twin Data Inspector"
    >
      {/* Header */}
      <div
        style={{
          padding: "1rem 1.25rem",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#1e293b",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              background: "#0d9488",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
            }}
          >
            <Code size={16} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "white", letterSpacing: "0.02em" }}>
                Data Inspector
              </span>
              <span
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 700,
                  background: "#0f766e",
                  color: "#99f6e4",
                  padding: "0.15rem 0.45rem",
                  borderRadius: "4px",
                }}
              >
                DEV MODE
              </span>
            </div>
            <div style={{ fontSize: "0.7rem", color: "#94a3b8", marginTop: "0.1rem" }}>
              Active Patient: <strong style={{ color: "#38bdf8" }}>{activePatientId}</strong> &bull; {twinState?.history?.length || 0} visits
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            title={expanded ? "Collapse panel width" : "Expand panel width"}
            style={{
              background: "transparent",
              border: "1px solid #334155",
              borderRadius: "4px",
              padding: "0.35rem",
              color: "#94a3b8",
              cursor: "pointer",
            }}
          >
            {expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close Data Inspector"
            style={{
              background: "transparent",
              border: "1px solid #334155",
              borderRadius: "4px",
              padding: "0.35rem",
              color: "#94a3b8",
              cursor: "pointer",
            }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Tab Selectors & Search Toolbar */}
      <div
        style={{
          padding: "0.75rem 1.25rem",
          background: "#0f172a",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          flexDirection: "column",
          gap: "0.6rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
          <div style={{ display: "flex", gap: "0.3rem" }}>
            {(
              [
                { id: "all", label: "All TwinState", icon: FileJson },
                { id: "static", label: "Static", icon: Database },
                { id: "current", label: "Current", icon: Layers },
                { id: "history", label: `History (${twinState?.history?.length || 0})`, icon: Layers },
              ] as const
            ).map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    background: isActive ? "#0d9488" : "#1e293b",
                    color: isActive ? "white" : "#94a3b8",
                    border: "none",
                    borderRadius: "4px",
                    padding: "0.3rem 0.55rem",
                    fontSize: "0.72rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.3rem",
                    transition: "all 0.15s ease",
                  }}
                >
                  <Icon size={12} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={handleCopy}
            style={{
              background: copied ? "#059669" : "#1e293b",
              color: copied ? "white" : "#94a3b8",
              border: "1px solid #334155",
              borderRadius: "4px",
              padding: "0.3rem 0.6rem",
              fontSize: "0.72rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
            }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied JSON" : "Copy JSON"}
          </button>
        </div>

        {/* Search Bar */}
        <div style={{ position: "relative" }}>
          <Search
            size={13}
            style={{ position: "absolute", left: "0.6rem", top: "50%", transform: "translateY(-50%)", color: "#64748b" }}
          />
          <input
            type="text"
            placeholder="Filter keys or values (e.g. fev1_liters, gold_stage)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "4px",
              padding: "0.35rem 0.6rem 0.35rem 1.8rem",
              color: "white",
              fontSize: "0.75rem",
              outline: "none",
            }}
          />
        </div>
      </div>

      {/* JSON Viewer Body */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: "1rem 1.25rem",
          background: "#090d16",
          fontSize: "0.75rem",
          lineHeight: 1.5,
        }}
      >
        <pre
          style={{
            margin: 0,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            color: "#e2e8f0",
          }}
        >
          {filteredJsonString}
        </pre>
      </div>

      {/* Footer Info */}
      <div
        style={{
          padding: "0.6rem 1.25rem",
          borderTop: "1px solid #1e293b",
          background: "#0f172a",
          fontSize: "0.6875rem",
          color: "#64748b",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span>Live Reactive TwinState Audit Log</span>
        <span>Mutates automatically on new visit additions</span>
      </div>
    </div>
  );
}
