"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { useAdminSession } from "@/components/admin-session";
import { api, dateLabel, readable } from "@/lib/api";

type Run = {
  id: string;
  parent_run_id: string | null;
  target_program_id: string | null;
  draft_revision_id: string | null;
  superseded_by_revision_id: string | null;
  scheduled_source_id: string | null;
  scheduled_scan_id: string | null;
  discovered_candidate_id: string | null;
  source_url: string;
  source_method: string;
  state: string;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

type RunFilter = "current_review" | "superseded" | "awaiting_review" | "failed" | "published" | "all";

export default function IngestionPage() {
  const session = useAdminSession();
  const [runs, setRuns] = useState<Run[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [filter, setFilter] = useState<RunFilter>("current_review");
  const [showForm, setShowForm] = useState(false);
  const [method, setMethod] = useState("webpage");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setRuns(await api<Run[]>("/api/admin/ingestion-runs"));
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (session.status !== "authenticated") return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [session.status, load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session.csrf) return;
    const data = new FormData(event.currentTarget);
    setMessage("");
    try {
      await api("/api/admin/ingestion-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf },
        body: JSON.stringify({
          idempotency_key: data.get("key"),
          source_url: data.get("url"),
          source_method: method,
          source_text: method === "pasted_text" ? data.get("text") : null,
        }),
      });
      setShowForm(false);
      await load();
    } catch {
      setMessage("The ingestion run could not be created. Check the source and idempotency key.");
    }
  }

  async function retry(run: Run) {
    if (!session.csrf) return;
    try {
      await api(`/api/admin/ingestion-runs/${run.id}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf },
        body: JSON.stringify({ idempotency_key: `manual:${run.id}` }),
      });
      await load();
    } catch {
      setMessage("The failed run could not be retried.");
    }
  }

  const visibleRuns =
    filter === "all"
      ? runs
      : filter === "current_review"
        ? runs.filter((run) => run.state === "awaiting_review" && !run.superseded_by_revision_id)
        : filter === "superseded"
          ? runs.filter((run) => run.state === "awaiting_review" && Boolean(run.superseded_by_revision_id))
          : runs.filter((run) => run.state === filter);
  const awaitingCount = runs.filter((run) => run.state === "awaiting_review").length;
  const currentReviewCount = runs.filter((run) => run.state === "awaiting_review" && !run.superseded_by_revision_id).length;
  const supersededCount = runs.filter((run) => run.state === "awaiting_review" && Boolean(run.superseded_by_revision_id)).length;
  const failedCount = runs.filter((run) => run.state === "failed").length;
  const publishedCount = runs.filter((run) => run.state === "published").length;

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Human-reviewed workflow</p>
          <h1>Ingestion runs</h1>
          <p>Inspect manual and scheduled source processing before publication.</p>
        </div>
        <button className="button button-primary" onClick={() => setShowForm((value) => !value)}>
          {showForm ? "Cancel" : "New ingestion"}
        </button>
      </div>

      {showForm && (
        <form className="admin-form" onSubmit={submit}>
          <label>
            Idempotency key
            <input name="key" required />
          </label>
          <label>
            Official source URL
            <input name="url" type="url" required />
          </label>
          <label>
            Source method
            <select value={method} onChange={(event) => setMethod(event.target.value)}>
              <option value="webpage">Webpage</option>
              <option value="pasted_text">Pasted text</option>
            </select>
          </label>
          {method === "pasted_text" && (
            <label className="full-field">
              Source text
              <textarea name="text" rows={8} required />
            </label>
          )}
          <button className="button button-primary">Create run</button>
        </form>
      )}

      {message && (
        <div className="form-error" role="alert">
          {message}
        </div>
      )}

      {state === "loading" && <div className="skeleton-panel" />}
      {state === "error" && (
        <section className="empty-panel">
          <h2>Runs unavailable</h2>
          <button className="button button-primary" onClick={() => void load()}>
            Try again
          </button>
        </section>
      )}
      {state === "ready" && runs.length === 0 && (
        <section className="empty-panel">
          <h2>No ingestion runs</h2>
          <p>Create a manual run or wait for the scheduler to discover work.</p>
        </section>
      )}

      {state === "ready" && runs.length > 0 && (
        <>
          <div className="admin-toolbar">
            <label>
              Show runs
              <select value={filter} onChange={(event) => setFilter(event.target.value as RunFilter)}>
                <option value="current_review">Current drafts ({currentReviewCount})</option>
                <option value="superseded">Superseded drafts ({supersededCount})</option>
                <option value="awaiting_review">All awaiting review ({awaitingCount})</option>
                <option value="failed">Failed attempts ({failedCount})</option>
                <option value="published">Published ({publishedCount})</option>
                <option value="all">All history ({runs.length})</option>
              </select>
            </label>
          </div>

          {visibleRuns.length === 0 ? (
            <section className="empty-panel">
              <h2>No runs in this view</h2>
            </section>
          ) : (
            <div className="admin-list">
              {visibleRuns.map((run) => (
                <article className="run-row" key={run.id}>
                  <div>
                    <div className="pill-row">
                      <span className={`status-pill ${run.state === "failed" ? "status-false" : run.state === "published" ? "status-true" : ""}`}>
                        {readable(run.state)}
                      </span>
                      <span className="info-pill">{run.scheduled_source_id ? "Scheduled" : "Manual"}</span>
                      {run.discovered_candidate_id && <span className="info-pill">Discovered candidate</span>}
                      {run.superseded_by_revision_id && <span className="info-pill">Superseded draft</span>}
                    </div>
                    <h2>{run.source_url}</h2>
                    <p>
                      Created {dateLabel(run.created_at)}
                      {run.error_message ? ` · ${run.error_message}` : ""}
                    </p>
                  </div>
                  <div className="row-actions">
                    {run.state === "failed" && (
                      <button className="button button-outline" onClick={() => void retry(run)}>
                        Retry
                      </button>
                    )}
                    {run.draft_revision_id && (
                      <Link className="button button-primary" href={`/admin/revisions/${run.draft_revision_id}`}>
                        Review draft
                      </Link>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
