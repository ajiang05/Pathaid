"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { openWithApplicationCopilot } from "@/lib/application-copilot";
import { ResultCard } from "@/components/result-card";
import type { LocalStatus, MatchesResponse } from "@/types/api";

export default function DiscoverPage() {
  const [data, setData] = useState<MatchesResponse | null>(null);
  const [extensionId, setExtensionId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    api<MatchesResponse>("/api/matches").then(setData).catch(() => setFailed(true));
    api<LocalStatus>("/api/local/status").then(status => setExtensionId(status.extension_id)).catch(() => undefined);
  }, []);
  const load = () => {
    setFailed(false);
    api<MatchesResponse>("/api/matches").then(setData).catch(() => setFailed(true));
  };
  const groups = useMemo(() => ({
    strong: data?.results.filter(item => item.match_label === "Strong match") ?? [],
    possible: data?.results.filter(item => item.match_label === "Possible match") ?? [],
    automatic: data?.automatically_considered ?? [],
    sweepstakes: data?.sweepstakes ?? [],
  }), [data]);
  async function setStatus(scholarshipId: string, status: "not_started" | "in_progress") {
    await api(`/api/saved-scholarships/${scholarshipId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
    });
    setData(current => current ? {
      ...current,
      results: current.results.map(item => item.scholarship_id === scholarshipId ? { ...item, saved_status: status } : item),
    } : current);
  }
  async function apply(result: MatchesResponse["results"][number]) {
    // Open synchronously from the click so popup blockers recognize user intent.
    const application = window.open("about:blank", "_blank");
    // Sever access back to PathAid before navigating to an external sponsor.
    if (application) application.opener = null;
    try {
      if (await openWithApplicationCopilot(extensionId, result.scholarship_id)) {
        application?.close();
        setData(current => current ? {
          ...current,
          results: current.results.map(item => item.scholarship_id === result.scholarship_id ? { ...item, saved_status: "in_progress" } : item),
        } : current);
        return;
      }
      await setStatus(result.scholarship_id, "in_progress");
      if (application) application.location.href = result.application_url;
      else window.location.assign(result.application_url);
    } catch (error) {
      application?.close();
      throw error;
    }
  }
  async function skip(scholarshipId: string) {
    await api(`/api/scholarships/${scholarshipId}/skip`, { method: "PUT" });
    setData(current => current ? { ...current, results: current.results.filter(item => item.scholarship_id !== scholarshipId) } : current);
  }
  const card = (item: MatchesResponse["results"][number]) => <ResultCard
    key={item.scholarship_id}
    result={item}
    onSave={() => setStatus(item.scholarship_id, "not_started")}
    onApply={() => apply(item)}
    onSkip={() => skip(item.scholarship_id)}
  />;
  return <>
    <div className="page-heading"><div><p className="eyebrow">Current verified scholarships</p><h1>Discover</h1><p>Results come only from your saved profile. PathAid never asks follow-up questions on this page.</p></div></div>
    {!data && !failed && <section className="skeleton-panel" aria-label="Loading scholarship matches" />}
    {failed && <section className="empty-panel"><h2>Matches unavailable</h2><p>Check that the local backend is running.</p><button className="button button-primary" onClick={load}>Try again</button></section>}
    {data?.catalog_status === "awaiting_approved_sources" && <section className="empty-panel"><h2>No verified scholarships yet</h2><p>Confirm and scan official sources to build the local catalog. PathAid does not insert fake opportunities or show unvalidated extractions.</p><Link className="button button-outline" href="/sources">Manage sources</Link></section>}
    {data?.catalog_status === "ready" && data.results.length + data.automatically_considered.length + data.sweepstakes.length === 0 && <section className="empty-panel"><h2>No current verified matches</h2><p>This is not a finding that you are ineligible. It reflects the current source coverage.</p></section>}
    {groups.strong.length > 0 && <section><div className="section-heading"><h2>Strong matches</h2><span>{groups.strong.length}</span></div><div className="result-grid">{groups.strong.map(card)}</div></section>}
    {groups.possible.length > 0 && <section><div className="section-heading"><h2>Possible matches</h2><span>{groups.possible.length}</span></div><p className="missing-note">At least one hard requirement is unknown. Add details in Profile to improve precision.</p><div className="result-grid">{groups.possible.map(card)}</div></section>}
    {groups.automatic.length > 0 && <section><div className="section-heading"><h2>Automatically considered</h2><span>{groups.automatic.length}</span></div><p className="missing-note">The official source says eligible students are considered without a separate application. PathAid does not create a misleading application status.</p><div className="result-grid">{groups.automatic.map(card)}</div></section>}
    {groups.sweepstakes.length > 0 && <section><div className="section-heading"><h2>Verified sweepstakes</h2><span>{groups.sweepstakes.length}</span></div><p className="missing-note">These easy-entry awards have a verified public official-rules page. Review the rules before entering.</p><div className="result-grid">{groups.sweepstakes.map(card)}</div></section>}
  </>;
}
