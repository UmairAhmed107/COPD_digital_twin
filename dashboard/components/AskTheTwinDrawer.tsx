"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Send,
  Sparkles,
  Bot,
  User,
  AlertCircle,
  HelpCircle,
  RefreshCw,
} from "lucide-react";
import { askTwinQuestion } from "../lib/api";
import { TwinStateResponse } from "../lib/types";

interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
  timestamp: string;
  isError?: boolean;
}

interface AskTheTwinDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  patientId: string;
  twinState: TwinStateResponse | null;
}

const QUICK_PROMPTS = [
  "Why is FEV1 projected to decline?",
  "What is the projected 2-year benefit of smoking cessation?",
  "How does increasing physical activity impact FEV1?",
  "What are the primary longitudinal risk factors?",
];

export default function AskTheTwinDrawer({
  isOpen,
  onClose,
  patientId,
  twinState,
}: AskTheTwinDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Initialize consultation messages when patient changes or drawer opens
  useEffect(() => {
    if (!isOpen) return;

    const goldStage = twinState?.static?.gold_stage_baseline || "II";
    const visitsCount = twinState?.history?.length || 1;
    const currentFEV1 = twinState?.current?.fev1_liters
      ? Number(twinState.current.fev1_liters).toFixed(2)
      : "1.85";

    setMessages([
      {
        id: "welcome-msg",
        sender: "ai",
        text: `Welcome to the Virtual Pulmonary Consultation for Patient ${patientId}. I have ingested their baseline profile (GOLD Stage ${goldStage}), ${visitsCount} documented longitudinal visits (latest observed FEV1: ${currentFEV1} L), and projected 24-month trajectories. Ask any clinical question regarding progression drivers or intervention what-ifs.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);

    // Focus input after opening
    setTimeout(() => {
      inputRef.current?.focus();
    }, 150);
  }, [isOpen, patientId]);

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSendMessage = async (textToSend?: string) => {
    const question = (textToSend || inputQuestion).trim();
    if (!question || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: question,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion("");
    setLoading(true);

    try {
      const response = await askTwinQuestion(patientId, question);
      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: "ai",
        text: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const isMissingKey = err.message && err.message.includes("GEMINI_API_KEY");
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "ai",
        text: isMissingKey
          ? "The Gemini API key is not configured on the backend server. Please set GEMINI_API_KEY in your environment or launch scripts to enable live pulmonary narrative inference."
          : (err.message || "Failed to generate AI consultation answer. Please verify backend connectivity."),
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="drawer-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Drawer Panel */}
      <aside
        className="drawer-container"
        role="dialog"
        aria-modal="true"
        aria-label={`Virtual Pulmonologist Consultation for Patient ${patientId}`}
      >
        {/* Header */}
        <div className="drawer-header">
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div className="brand-icon" style={{ width: "36px", height: "36px", background: "var(--teal-primary)" }}>
              <Sparkles size={18} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
                  Ask the Twin
                </h2>
                <span className="ai-badge">
                  <span className="ai-badge-pulse" />
                  Gemini Grounded
                </span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.1rem" }}>
                Pulmonary Consultation &bull; Patient {patientId}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close consultation drawer"
            style={{
              background: "transparent",
              border: "1px solid var(--border-light)",
              borderRadius: "var(--radius-md)",
              padding: "0.4rem",
              cursor: "pointer",
              color: "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body - Message Stream */}
        <div className="drawer-body">
          {/* Quick Prompts Bar */}
          <div style={{ paddingBottom: "0.5rem" }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
              Suggested Clinical Inquiries
            </div>
            <div className="prompt-chips-wrapper">
              {QUICK_PROMPTS.map((prompt, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="prompt-chip-btn"
                  onClick={() => handleSendMessage(prompt)}
                  disabled={loading}
                >
                  <HelpCircle size={13} style={{ color: "var(--teal-primary)" }} />
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Messages */}
          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message-row ${msg.sender}`}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.15rem" }}>
                {msg.sender === "ai" ? (
                  <>
                    <Bot size={13} color="var(--teal-primary)" />
                    <span className="chat-meta">Pulmonology Assistant</span>
                  </>
                ) : (
                  <>
                    <span className="chat-meta">Clinician</span>
                    <User size={13} color="var(--text-secondary)" />
                  </>
                )}
                <span className="chat-meta">&bull; {msg.timestamp}</span>
              </div>

              <div className={`chat-bubble ${msg.sender} ${msg.isError ? "error" : ""}`}>
                {msg.isError && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.3rem", fontWeight: 600 }}>
                    <AlertCircle size={14} /> Advisory Notice
                  </div>
                )}
                <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
              </div>
            </div>
          ))}

          {/* Loading Indicator */}
          {loading && (
            <div className="chat-message-row ai">
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.15rem" }}>
                <Bot size={13} color="var(--teal-primary)" />
                <span className="chat-meta">Analyzing Digital Twin...</span>
              </div>
              <div className="chat-bubble ai" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <RefreshCw size={14} className="animate-spin" color="var(--teal-primary)" />
                <span>Evaluating longitudinal observations and trajectory models...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Footer Input */}
        <div className="drawer-footer">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            style={{ display: "flex", gap: "0.5rem" }}
          >
            <input
              ref={inputRef}
              type="text"
              className="form-input"
              style={{ flex: 1, padding: "0.6rem 0.85rem", fontSize: "0.8125rem" }}
              placeholder="Ask about lung function, risk factors, or interventions..."
              value={inputQuestion}
              onChange={(e) => setInputQuestion(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !inputQuestion.trim()}
              style={{ padding: "0.6rem 1rem", fontSize: "0.8125rem" }}
            >
              {loading ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
              Send
            </button>
          </form>

          <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textAlign: "center" }}>
            Grounding enforced via strictly structured digital twin JSON payload &bull; Academic ML demo
          </div>
        </div>
      </aside>
    </>
  );
}
