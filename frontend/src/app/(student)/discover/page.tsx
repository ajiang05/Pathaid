"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { ResultCard } from "@/components/result-card";
import type { MatchesResponse } from "@/types/api";

export default function DiscoverPage() {
  const [data, setData] = useState<MatchesResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    api<MatchesResponse>("/api/matches").then(setData).catch(() => setFailed(true));
  }, []);
  const load = () => {
    setFailed(false);
    api<MatchesResponse>("/api/matches").then(setData).catch(() => setFailed(true));
  };
  const groups = useMemo(() => ({
    strong: data?.results.filter(item => item.match_label === "Strong match") ?? [],
    possible: data?.results.filter(item => item.match_label === "Possible match") ?? [],
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
    {data?.catalog_status === "ready" && data.results.length === 0 && <section className="empty-panel"><h2>No current verified matches</h2><p>This is not a finding that you are ineligible. It reflects the current source coverage.</p></section>}
    {groups.strong.length > 0 && <section><div className="section-heading"><h2>Strong matches</h2><span>{groups.strong.length}</span></div><div className="result-grid">{groups.strong.map(card)}</div></section>}
    {groups.possible.length > 0 && <section><div className="section-heading"><h2>Possible matches</h2><span>{groups.possible.length}</span></div><p className="missing-note">At least one hard requirement is unknown. Add details in Profile to improve precision.</p><div className="result-grid">{groups.possible.map(card)}</div></section>}
  </>;
}
