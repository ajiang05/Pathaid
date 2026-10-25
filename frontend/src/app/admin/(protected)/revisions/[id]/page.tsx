"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAdminSession } from "@/components/admin-session";
import { api, readable } from "@/lib/api";

type ValidationFinding = {
  code: string;
  path: string;
  message: string;
  severity: "error" | "warning";
};

type Revision = Record<string, unknown> & {
  status: string;
  validation_status: string;
  validation_findings: ValidationFinding[];
  provider_url: string;
  name: string;
  description: string;
};

type Review = {
  revision: Revision;
  proposed_draft: Record<string, unknown> | null;
  ingestion_run_id: string | null;
  sources: Array<{ id: string; source_url: string; source_text: string; acquired_at: string }>;
  review_events: Array<{
    id: string;
    reviewer: string;
    decision: string;
    notes: string | null;
    created_at: string;
  }>;
};

export default function RevisionPage() {
  const { id } = useParams<{ id: string }>();
  const session = useAdminSession();
  const [data, setData] = useState<Review | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [editMessage, setEditMessage] = useState("");
  const [editFailed, setEditFailed] = useState(false);
  const [decisionMessage, setDecisionMessage] = useState("");
  const [decisionFailed, setDecisionFailed] = useState(false);
  const [decisionPending, setDecisionPending] = useState(false);
  const [draft, setDraft] = useState("");
  const [notes, setNotes] = useState("");
  const [accurate, setAccurate] = useState(false);
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    if (session.status !== "authenticated") return;
    const timer = window.setTimeout(() => {
      api<Review>(`/api/admin/revisions/${id}`)
        .then((value) => {
          setData(value);
          setDraft(JSON.stringify(value.proposed_draft ?? value.revision, null, 2));
          setState("ready");
        })
        .catch(() => setState("error"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [id, session.status]);

  async function edit() {
    if (!session.csrf || !data) return;
    setEditMessage("");
    setEditFailed(false);
    try {
      const parsed = JSON.parse(draft) as Record<string, unknown>;
      const updated = await api<Revision>(`/api/admin/revisions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf },
        body: JSON.stringify({ draft: parsed, provider_url: data.revision.provider_url }),
      });
      // Keep the displayed status and findings in sync with server-side
      // revalidation so the reviewer sees whether another edit is required.
      setData((current) =>
        current
          ? { ...current, revision: { ...current.revision, ...updated }, proposed_draft: parsed }
          : current,
      );
      setEditMessage("Draft saved and revalidated.");
    } catch {
      setEditFailed(true);
      setEditMessage("The draft JSON or reviewed evidence is invalid. Changes were not published.");
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!session.csrf || decisionPending) return;
    setDecisionFailed(false);
    setDecisionPending(true);
    setDecisionMessage(decision === "approve" ? "Publishing revision…" : "Rejecting revision…");
    try {
      await api(`/api/admin/revisions/${id}/${decision}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf },
        body: JSON.stringify(decision === "approve" ? { source_accurate: accurate, coverage_complete: complete, notes } : { notes }),
      });
      setDecisionMessage(decision === "approve" ? "Revision published." : "Revision rejected.");
      setData((current) =>
        current
          ? {
              ...current,
              revision: { ...current.revision, status: decision === "approve" ? "published" : "rejected" },
            }
          : current,
      );
    } catch {
      setDecisionFailed(true);
      setDecisionMessage(`The revision could not be ${decision === "approve" ? "published" : "rejected"}. Check validation and attestations.`);
    } finally {
      setDecisionPending(false);
    }
  }

  if (state === "loading") return <div className="skeleton-panel" />;
  if (state === "error" || !data) {
    return (
      <section className="empty-panel">
        <h1>Revision unavailable</h1>
      </section>
    );
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Review and publication</p>
          <h1>{data.revision.name}</h1>
          <p>
            Status: {readable(data.revision.status)} · Validation: {readable(data.revision.validation_status)}
          </p>
        </div>
      </div>

      {data.revision.validation_findings.length > 0 && (
        <section className="detail-card" aria-labelledby="validation-findings-heading">
          <h2 id="validation-findings-heading">Validation findings</h2>
          <ul>
            {data.revision.validation_findings.map((finding) => (
              <li key={`${finding.code}:${finding.path}`}>
                <strong>{readable(finding.severity)}:</strong> {finding.message} <small>Field: {finding.path}</small>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="review-grid">
        <section className="detail-card">
          <h2>Retained official source</h2>
          {data.sources.map((source) => (
            <article key={source.id}>
              <a className="source-link" href={source.source_url} target="_blank" rel="noopener noreferrer">
                {source.source_url} ↗
              </a>
              <pre className="source-text">{source.source_text}</pre>
            </article>
          ))}
        </section>

        <section className="detail-card">
          <h2 id="structured-proposal-heading">Editable structured proposal</h2>
          <p>Edits rerun deterministic source-evidence validation.</p>
          <textarea
            aria-labelledby="structured-proposal-heading"
            className="json-editor"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            spellCheck={false}
          />
          <button className="button button-outline" onClick={() => void edit()} disabled={data.revision.status !== "draft"}>
            Save and revalidate
          </button>
          {editMessage && (
            <div className={editFailed ? "form-error" : "form-success"} role={editFailed ? "alert" : "status"}>
              {editMessage}
            </div>
          )}
        </section>
      </div>

      <section className="review-decision" aria-labelledby="review-decision-heading">
        <h2 id="review-decision-heading">Review decision</h2>
        <label className="consent-option">
          <input type="checkbox" checked={accurate} onChange={(event) => setAccurate(event.target.checked)} />
          <span>
            <strong>I verified the proposal against the retained source</strong>
          </span>
        </label>
        <label className="consent-option">
          <input type="checkbox" checked={complete} onChange={(event) => setComplete(event.target.checked)} />
          <span>
            <strong>Reviewed eligibility coverage is complete</strong>
            <small>Leave unchecked if provider-only or unsupported requirements remain.</small>
          </span>
        </label>
        <label>
          Review notes
          <textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} />
        </label>
        {decisionMessage && (
          <div className={decisionFailed ? "form-error" : "form-success"} role={decisionFailed ? "alert" : "status"} aria-live="polite">
            {decisionMessage}
          </div>
        )}
        <div className="row-actions">
          <button className="button button-danger" disabled={data.revision.status !== "draft" || decisionPending} onClick={() => void decide("reject")}>
            {decisionPending ? "Working…" : "Reject draft"}
          </button>
          <button
            className="button button-primary"
            disabled={data.revision.status !== "draft" || data.revision.validation_status !== "valid" || !accurate || decisionPending}
            onClick={() => void decide("approve")}
          >
            {decisionPending ? "Working…" : "Approve and publish"}
          </button>
        </div>
      </section>
    </>
  );
}
