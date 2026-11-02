"use client";

import { useState } from "react";
import { readable } from "@/lib/api";
import type { MatchResult } from "@/types/api";

function deadline(value: string | null) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(value));
}

type ResultCardProps = {
  result: MatchResult;
  onSave: () => Promise<void>;
  onApply: () => Promise<void>;
  onSkip: () => Promise<void>;
};

export function ResultCard({ result, onSave, onApply, onSkip }: ResultCardProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const statusClass = result.match_label === "Strong match" ? "status-true" : "status-pill";
  async function act(action: () => Promise<void>, success: string) {
    setBusy(true); setMessage("");
    try { await action(); setMessage(success); }
    catch { setMessage("That action could not be completed."); }
    finally { setBusy(false); }
  }
  return <article className="result-card">
    <header className="result-top"><p className="result-provider">{result.sponsor}</p><h3>{result.name}</h3></header>
    <dl className="result-facts"><div><dt>Award</dt><dd>{result.award ?? "Not stated"}</dd></div><div><dt>Deadline</dt><dd>{deadline(result.deadline)}</dd></div><div><dt>Eligibility</dt><dd>{result.match_label}</dd></div></dl>
    <div className="pill-row"><span className={`status-pill ${statusClass}`}>{result.match_label}</span></div>
    {result.key_reasons.length > 0 && <ul className="missing-note">{result.key_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
    {result.unknown_fields.length > 0 && <p className="missing-note">Unknown: {result.unknown_fields.map(readable).join(", ")}</p>}
    <footer className="result-actions">
      <button className="button button-outline" disabled={busy} onClick={() => act(onSave, "Saved as Not started.")}>{result.saved_status ? "Saved" : "Save"}</button>
      <button className="button button-primary" disabled={busy} onClick={() => act(onApply, "Marked In progress and opened the official application.")}>Apply</button>
      <button className="text-action" disabled={busy} onClick={() => act(onSkip, "Hidden until this scholarship materially changes.")}>Skip this cycle</button>
    </footer>
    <p className="action-message" role="status" aria-live="polite">{message}</p>
  </article>;
}
