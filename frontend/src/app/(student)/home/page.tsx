"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/types/api";

export default function HomePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { api<Profile>("/api/profile").then(setProfile).catch(() => setFailed(true)); }, []);
  if (failed) return <section className="empty-panel"><h1>PathAid is unavailable</h1><p>Start the local backend, then refresh this page.</p></section>;
  if (!profile) return <section className="skeleton-panel" aria-label="Loading local profile" />;
  const ready = profile.completeness.known > 0;
  return <>
    <div className="page-heading"><div><p className="eyebrow">Private on this Mac</p><h1>{ready ? "Your scholarship search" : "Build your scholarship profile"}</h1><p>PathAid compares saved local answers with official scholarship requirements. Gemini does not decide your eligibility.</p></div></div>
    <section className="dashboard-grid">
      <article className="metric-card"><span>Profile completeness</span><strong>{profile.completeness.percent_known}%</strong><p>{profile.completeness.known} known · {profile.completeness.unknown} marked unknown</p></article>
      <article className="metric-card"><span>Matching</span><strong>Deterministic</strong><p>Hard requirements produce Strong, Possible, or Not a match.</p></article>
      <article className="metric-card"><span>Data location</span><strong>Local</strong><p>Your private profile is stored in the SQLite database on this Mac.</p></article>
      <div className="wide-card"><h2>{ready ? "Review current matches" : "Complete your profile first"}</h2><p>More optional answers reduce Possible matches, but no question blocks discovery.</p><Link className="button button-primary" href={ready ? "/discover" : "/profile"}>{ready ? "Open Discover" : "Build profile"}</Link></div>
    </section>
  </>;
}
