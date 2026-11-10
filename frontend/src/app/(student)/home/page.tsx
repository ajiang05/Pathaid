"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HomeSummary } from "@/types/api";

export default function HomePage() {
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { api<HomeSummary>("/api/home-summary").then(setSummary).catch(() => setFailed(true)); }, []);
  if (failed) return <section className="empty-panel"><h1>PathAid is unavailable</h1><p>Start the local backend, then refresh this page.</p></section>;
  if (!summary) return <section className="skeleton-panel" aria-label="Loading local status" />;
  const ready = summary.profile_completeness.known > 0;
  return <>
    <div className="page-heading"><div><p className="eyebrow">Private on this Mac</p><h1>{ready ? "Your scholarship search" : "Build your scholarship profile"}</h1><p>PathAid compares saved local answers with official scholarship requirements. Gemini does not decide your eligibility.</p></div></div>
    <section className="dashboard-grid">
      <article className="metric-card"><span>Profile completeness</span><strong>{summary.profile_completeness.percent_known}%</strong><p>{summary.profile_completeness.known} known · {summary.profile_completeness.unknown} marked unknown</p></article>
      <article className="metric-card"><span>Discovery sources</span><strong>{summary.active_sources} active</strong><p>{summary.due_sources} due · {summary.paused_sources} paused</p></article>
      <article className="metric-card"><span>Verified scholarships</span><strong>{summary.active_scholarships}</strong><p>{summary.last_success_at ? `Last successful scan ${new Date(summary.last_success_at).toLocaleString()}` : "No successful source scan yet"}</p></article>
      <div className="wide-card"><h2>{ready ? "Review current matches" : "Complete your profile first"}</h2><p>More optional answers reduce Possible matches, but no question blocks discovery.</p><Link className="button button-primary" href={ready ? "/discover" : "/profile"}>{ready ? "Open Discover" : "Build profile"}</Link></div>
      {summary.alerts.length > 0 && <div className="wide-card"><h2>Needs attention</h2><ul>{summary.alerts.map(alert => <li key={alert.code}><Link className="text-link" href={alert.href}>{alert.message}</Link></li>)}</ul></div>}
    </section>
  </>;
}
