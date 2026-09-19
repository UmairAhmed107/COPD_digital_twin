"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { Search, X, User, Check, RefreshCw, AlertCircle } from "lucide-react";
import { getPatients } from "../lib/api";
import { PatientSummary } from "../lib/types";

interface PatientSearchBarProps {
  selectedPatientId?: string;
  onSelectPatientId: (id: string) => void;
  placeholder?: string;
  className?: string;
}

export default function PatientSearchBar({
  selectedPatientId,
  onSelectPatientId,
  placeholder = "Search cohort (e.g., P0042, GOLD III, Smoker, Female)...",
  className = "",
}: PatientSearchBarProps) {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<string>("");
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [activeIndex, setActiveIndex] = useState<number>(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Fetch full cohort directory dynamically on mount (no 50-item cap)
  useEffect(() => {
    let isMounted = true;
    async function loadAllPatients() {
      setLoading(true);
      setError(null);
      try {
        const data = await getPatients();
        if (isMounted) {
          setPatients(data || []);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Failed to load patients");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }
    loadAllPatients();
    return () => {
      isMounted = false;
    };
  }, []);

  // Multi-token fuzzy filtering
  const filteredPatients = useMemo(() => {
    if (!query.trim()) {
      return patients;
    }
    const tokens = query.trim().toLowerCase().split(/\s+/);
    return patients.filter((p) => {
      const pid = p.patient_id.toLowerCase();
      const sum = (p.summary || "").toLowerCase();
      const combined = `${pid} ${sum}`;
      // Every typed token must be found in the patient's id or summary
      return tokens.every((token) => combined.includes(token));
    });
  }, [patients, query]);

  // Click outside listener to dismiss dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setActiveIndex(-1);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Reset active index whenever results change
  useEffect(() => {
    setActiveIndex(filteredPatients.length > 0 ? 0 : -1);
  }, [filteredPatients]);

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const activeItem = listRef.current.children[activeIndex] as HTMLElement;
      if (activeItem) {
        activeItem.scrollIntoView({ block: "nearest" });
      }
    }
  }, [activeIndex]);

  const handleSelect = (patient: PatientSummary) => {
    onSelectPatientId(patient.patient_id);
    setQuery("");
    setIsOpen(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        setIsOpen(true);
        return;
      }
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (filteredPatients.length === 0) return;
      setActiveIndex((prev) => (prev + 1) % filteredPatients.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (filteredPatients.length === 0) return;
      setActiveIndex((prev) => (prev - 1 + filteredPatients.length) % filteredPatients.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIndex >= 0 && activeIndex < filteredPatients.length) {
        handleSelect(filteredPatients[activeIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
    }
  };

  // Currently selected patient summary for preview placeholder
  const activePatientSummary = useMemo(() => {
    if (!selectedPatientId) return null;
    return patients.find((p) => p.patient_id === selectedPatientId);
  }, [patients, selectedPatientId]);

  return (
    <div
      ref={containerRef}
      className={`patient-search-container ${className}`}
      style={{
        position: "relative",
        width: "100%",
        minWidth: "260px",
        maxWidth: "480px",
      }}
    >
      {/* Input wrapper */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          backgroundColor: "var(--bg-surface)",
          border: isOpen ? "1.5px solid var(--teal-primary)" : "1px solid var(--border-light)",
          borderRadius: "var(--radius-md)",
          padding: "0.4rem 0.75rem",
          gap: "0.5rem",
          boxShadow: isOpen
            ? "0 0 0 3px rgba(13, 148, 136, 0.15)"
            : "0 1px 2px rgba(0, 0, 0, 0.03)",
          transition: "all 0.15s ease",
        }}
      >
        <Search
          size={16}
          style={{
            color: isOpen ? "var(--teal-primary)" : "var(--text-muted)",
            flexShrink: 0,
            transition: "color 0.15s ease",
          }}
        />

        <input
          ref={inputRef}
          type="text"
          id="global-patient-search-input"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={
            activePatientSummary
              ? `${activePatientSummary.patient_id} — ${activePatientSummary.summary}`
              : placeholder
          }
          style={{
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: "0.8125rem",
            color: "var(--text-primary)",
            width: "100%",
            padding: 0,
          }}
        />

        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setActiveIndex(-1);
              inputRef.current?.focus();
            }}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              padding: "2px",
              color: "var(--text-muted)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "50%",
            }}
            title="Clear search"
          >
            <X size={14} />
          </button>
        )}

        {loading && (
          <RefreshCw
            size={14}
            className="animate-spin"
            style={{ color: "var(--teal-primary)", flexShrink: 0 }}
          />
        )}
      </div>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-light)",
            borderRadius: "var(--radius-md)",
            boxShadow:
              "0 10px 25px -5px rgba(0, 0, 0, 0.12), 0 8px 10px -6px rgba(0, 0, 0, 0.08)",
            zIndex: 100,
            maxHeight: "320px",
            overflowY: "auto",
            animation: "fadeIn 0.12s ease-out",
          }}
        >
          {/* Header count info */}
          <div
            style={{
              padding: "0.5rem 0.75rem",
              borderBottom: "1px solid var(--border-light)",
              fontSize: "0.6875rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--text-muted)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              backgroundColor: "var(--bg-surface-secondary)",
            }}
          >
            <span>Cohort Directory</span>
            <span>
              {filteredPatients.length} of {patients.length} patients
            </span>
          </div>

          {error ? (
            <div
              style={{
                padding: "1rem",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                color: "var(--rose-primary)",
                fontSize: "0.75rem",
              }}
            >
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          ) : filteredPatients.length === 0 ? (
            <div
              style={{
                padding: "1.25rem 0.75rem",
                textAlign: "center",
                color: "var(--text-muted)",
                fontSize: "0.8125rem",
              }}
            >
              No patients found matching &ldquo;{query}&rdquo;
            </div>
          ) : (
            <ul
              ref={listRef}
              style={{
                listStyle: "none",
                margin: 0,
                padding: "0.25rem 0",
              }}
            >
              {filteredPatients.map((patient, idx) => {
                const isSelected = selectedPatientId === patient.patient_id;
                const isHighlighted = idx === activeIndex;

                return (
                  <li
                    key={patient.patient_id}
                    onClick={() => handleSelect(patient)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    style={{
                      padding: "0.55rem 0.75rem",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "0.5rem",
                      backgroundColor: isHighlighted
                        ? "var(--teal-light)"
                        : isSelected
                        ? "rgba(13, 148, 136, 0.05)"
                        : "transparent",
                      borderLeft: isSelected
                        ? "3px solid var(--teal-primary)"
                        : isHighlighted
                        ? "3px solid var(--teal-border)"
                        : "3px solid transparent",
                      transition: "background-color 0.1s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", overflow: "hidden" }}>
                      <div
                        style={{
                          width: "24px",
                          height: "24px",
                          borderRadius: "var(--radius-sm)",
                          backgroundColor: isSelected ? "var(--teal-primary)" : "var(--bg-surface-secondary)",
                          color: isSelected ? "#ffffff" : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          fontSize: "0.6875rem",
                          fontWeight: 700,
                        }}
                      >
                        <User size={13} />
                      </div>

                      <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <span
                            style={{
                              fontWeight: 700,
                              fontSize: "0.8125rem",
                              color: isSelected ? "var(--teal-primary)" : "var(--text-primary)",
                            }}
                          >
                            {patient.patient_id}
                          </span>
                          {isSelected && (
                            <span
                              style={{
                                fontSize: "0.625rem",
                                fontWeight: 700,
                                padding: "0.1rem 0.35rem",
                                borderRadius: "var(--radius-full)",
                                backgroundColor: "var(--teal-light)",
                                color: "var(--teal-primary)",
                                border: "1px solid var(--teal-border)",
                              }}
                            >
                              Active
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-secondary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {patient.summary}
                        </div>
                      </div>
                    </div>

                    {isSelected && (
                      <Check
                        size={15}
                        style={{ color: "var(--teal-primary)", flexShrink: 0 }}
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
