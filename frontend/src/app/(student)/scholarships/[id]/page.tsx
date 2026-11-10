"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, dateLabel, readable } from "@/lib/api";
import { openWithApplicationCopilot } from "@/lib/application-copilot";
import type { LocalStatus, ScholarshipDetail } from "@/types/api";

export default function ScholarshipDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<ScholarshipDetail | null>(null);
  const [extensionId, setExtensionId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setFailed(false);
    api<ScholarshipDetail>(`/api/scholarships/${encodeURIComponent(id)}`).then(setDetail).catch(() => setFailed(true));
  };
  useEffect(() => {
    api<ScholarshipDetail>(`/api/scholarships/${encodeURIComponent(id)}`).then(setDetail).catch(() => setFailed(true));
    api<LocalStatus>("/api/local/status").then(status => setExtensionId(status.extension_id)).catch(() => undefined);
  }, [id]);

  async function act(action: () => Promise<void>, success: string) {
    setBusy(true); setMessage("");
    try { await action(); setMessage(success); }
    catch (error) { setMessage(error instanceof Error ? error.message : "That action could not be completed."); }
    finally { setBusy(false); }
  }

  async function save(status: "not_started" | "in_progress") {
    await api(`/api/saved-scholarships/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
    });
    setDetail(current => current && ({ ...current, saved_status: status }));
  }

  async function apply() {
    if (!detail) return;
    const application = window.open("about:blank", "_blank");
    if (application) application.opener = null;
    try {
      if (await openWithApplicationCopilot(extensionId, id)) {
        application?.close(); setDetail(current => current && ({ ...current, saved_status: "in_progress" })); return;
      }
      await save("in_progress");
      if (application) application.location.href = detail.application_url;
      else window.location.assign(detail.application_url);
    } catch (error) { application?.close(); throw error; }
  }

  async function skip() {
    await api(`/api/scholarships/${id}/skip`, { method: "PUT" });
    router.push("/discover");
  }

  if (failed) return <section className="empty-panel"><h1>Scholarship unavailable</h1><p>The active evidence-backed version could not be loaded.</p><button className="button button-primary" onClick={load}>Try again</button></section>;
  if (!detail) return <section className="skeleton-panel" aria-label="Loading scholarship details" />;
  const statusClass = detail.match_label === "Strong match" ? "status-true" : detail.match_label === "Not a match" ? "status-false" : "status-pill";

  return <>
    <Link className="text-link" href="/discover">← Back to Discover</Link>
    <section className="program-hero">
      <p className="verified-line">Verified from retained official evidence · refreshed {dateLabel(detail.source_freshness)}</p>
      <h1>{detail.name}</h1><p>{detail.description}</p>
      <div className="program-facts"><div><span>Sponsor</span><strong>{detail.sponsor}</strong></div><div><span>Award</span><strong>{detail.award ?? "Not stated"}</strong></div><div><span>Deadline</span><strong>{detail.deadline ? dateLabel(detail.deadline) : "Not stated"}</strong></div></div>
      <div className="pill-row"><span className={`status-pill ${statusClass}`}>{detail.match_label}</span><span className="info-pill">{readable(detail.availability)}</span>{detail.application_process !== "separate_application" && <span className="info-pill">{readable(detail.application_process)}</span>}</div>
      <div className="result-actions">
        {detail.application_process !== "automatically_considered" && <><button className="button button-outline" disabled={busy} onClick={() => void act(() => save("not_started"), "Saved as Not started.")}>{detail.saved_status ? "Saved" : "Save"}</button><button className="button button-primary" disabled={busy || detail.automation_policy === "blocked"} onClick={() => void act(apply, "Marked In progress and opened the official application.")}>{detail.application_process === "sweepstakes" ? "Enter" : "Apply"}</button></>}
        <button className="text-action" disabled={busy} onClick={() => void act(skip, "Hidden until this scholarship materially changes.")}>Skip this cycle</button>
      </div>
      <p className="action-message" role="status" aria-live="polite">{message}</p>
      {detail.automation_policy === "blocked" && <p className="notice">Official rules prohibit automated application assistance. Review and apply manually from the official source.</p>}
    </section>

    <div className="detail-grid"><div className="detail-main">
      <section className="detail-card"><h2>Eligibility requirements</h2>{!detail.coverage_complete && <p className="notice">Some official requirements could not be represented exactly, so this cannot be a Strong match.</p>}<div className="criteria-list">{detail.criteria.map((criterion, index) => <article key={`${criterion.field}-${index}`}><span className={`truth-mark truth-${criterion.truth}`} aria-label={criterion.truth}>{criterion.truth === "pass" ? "✓" : criterion.truth === "fail" ? "×" : "?"}</span><div><h3>{criterion.field ? readable(criterion.field) : "Needs official confirmation"}</h3><p>{criterion.reason}</p><blockquote>{criterion.evidence.excerpt}</blockquote></div></article>)}</div>{detail.criteria.length === 0 && <p>No machine-answerable hard requirements were stated.</p>}</section>
      <section className="detail-card"><h2>Selection factors</h2>{detail.selection_factors.length ? <ul>{detail.selection_factors.map(item => <li key={`${item.description}-${item.evidence.excerpt}`}>{item.description}<blockquote>{item.evidence.excerpt}</blockquote></li>)}</ul> : <p>No separate selection preferences were stated.</p>}</section>
      <section className="detail-card"><h2>Application materials</h2>{detail.checklist.length ? <div className="materials-grid">{detail.checklist.map(item => <article key={`${item.label}-${item.evidence.excerpt}`}><h3>{item.label}</h3><p>{item.required ? "Required" : "Optional"}</p><blockquote>{item.evidence.excerpt}</blockquote></article>)}</div> : <p>No materials were listed in the retained source.</p>}</section>
    </div><aside className="detail-aside">
      <section className="detail-card recommendation-card"><h2>Application method</h2><p>{detail.application_process === "automatically_considered" ? "The official source says no separate application is required." : "Review the official application and submit it personally."}</p>{detail.ai_assistance_policy === "blocked" && <small>Official rules prohibit AI assistance for this scholarship.</small>}</section>
      <section className="detail-card"><h2>Official links</h2><a className="source-link" href={detail.source_url} target="_blank" rel="noreferrer">Official scholarship source</a>{detail.official_rules_url && <a className="source-link" href={detail.official_rules_url} target="_blank" rel="noreferrer">Official rules</a>}{detail.application_process !== "automatically_considered" && <a className="source-link" href={detail.application_url} target="_blank" rel="noreferrer">Official application</a>}</section>
      <section className="detail-card trust-note"><h2>PathAid boundary</h2><p>Gemini structures public source facts. Your profile is evaluated locally and PathAid never submits the application.</p></section>
    </aside></div>
  </>;
}
