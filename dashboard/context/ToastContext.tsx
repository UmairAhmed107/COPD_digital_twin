"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

export type ToastType = "critical" | "warning" | "success" | "info";

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message: string;
  timestamp?: string;
  duration?: number;
}

interface ToastContextValue {
  showToast: (toast: Omit<ToastItem, "id">) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      const newToast: ToastItem = {
        ...toast,
        id,
        timestamp: toast.timestamp || timeStr,
      };

      setToasts((prev) => {
        // Keep up to 4 active toasts, avoiding exact title duplicates currently active
        const filtered = prev.filter((t) => t.title !== toast.title);
        return [...filtered, newToast].slice(-4);
      });

      const duration = toast.duration ?? (toast.type === "critical" ? 8000 : 5000);
      setTimeout(() => {
        dismissToast(id);
      }, duration);
    },
    [dismissToast]
  );

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}

      {/* Floating Live Alert Feed Dock */}
      <div
        id="toast-notification-feed"
        role="region"
        aria-label="Clinical Alerts"
        aria-live="polite"
        style={{
          position: "fixed",
          top: "1.25rem",
          right: "1.25rem",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
          maxWidth: "420px",
          width: "calc(100vw - 2.5rem)",
          pointerEvents: "none",
        }}
      >
        {toasts.map((toast) => {
          const isCritical = toast.type === "critical";
          const isWarning = toast.type === "warning";
          const isSuccess = toast.type === "success";

          let borderColor = "var(--border-light)";
          let bgColor = "#ffffff";
          let textColor = "var(--text-primary)";
          let iconColor = "var(--teal-primary)";
          let icon = <Info size={20} color={iconColor} />;

          if (isCritical) {
            borderColor = "#e11d48";
            bgColor = "#1e1b20"; // Dark high-contrast card
            textColor = "#ffffff";
            iconColor = "#fb7185";
            icon = <AlertOctagon size={22} color={iconColor} className="animate-pulse" />;
          } else if (isWarning) {
            borderColor = "#f59e0b";
            bgColor = "#fffbeb";
            textColor = "#78350f";
            iconColor = "#d97706";
            icon = <AlertTriangle size={20} color={iconColor} />;
          } else if (isSuccess) {
            borderColor = "#10b981";
            bgColor = "#f0fdf4";
            textColor = "#064e3b";
            iconColor = "#059669";
            icon = <CheckCircle2 size={20} color={iconColor} />;
          }

          return (
            <div
              key={toast.id}
              className="clinical-toast-item"
              style={{
                pointerEvents: "auto",
                backgroundColor: bgColor,
                border: `1.5px solid ${borderColor}`,
                borderRadius: "var(--radius-md)",
                padding: "0.85rem 1rem",
                boxShadow: isCritical
                  ? "0 10px 25px -5px rgba(225, 29, 72, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3)"
                  : "0 8px 20px -4px rgba(0, 0, 0, 0.12), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
                display: "flex",
                gap: "0.75rem",
                alignItems: "flex-start",
                animation: "toastSlideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ flexShrink: 0, marginTop: "2px" }}>{icon}</div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
                  <span
                    style={{
                      fontSize: "0.875rem",
                      fontWeight: 700,
                      color: isCritical ? "#fda4af" : textColor,
                      letterSpacing: "-0.01em",
                    }}
                  >
                    {toast.title}
                  </span>
                  {toast.timestamp && (
                    <span
                      style={{
                        fontSize: "0.6875rem",
                        color: isCritical ? "#94a3b8" : "var(--text-muted)",
                        flexShrink: 0,
                      }}
                    >
                      {toast.timestamp}
                    </span>
                  )}
                </div>

                <p
                  style={{
                    fontSize: "0.8125rem",
                    color: isCritical ? "#e2e8f0" : textColor,
                    marginTop: "0.25rem",
                    lineHeight: 1.4,
                  }}
                >
                  {toast.message}
                </p>
              </div>

              <button
                type="button"
                aria-label="Close notification"
                onClick={() => dismissToast(toast.id)}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: isCritical ? "#94a3b8" : "var(--text-muted)",
                  padding: "0.2rem",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "color 0.15s ease",
                  flexShrink: 0,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = isCritical ? "#ffffff" : "var(--text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = isCritical ? "#94a3b8" : "var(--text-muted)";
                }}
              >
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
