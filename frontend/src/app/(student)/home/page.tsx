"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/types/api";

export default function HomePage() {
  const [profile,setProfile]=useState<Profile|null>(null); const [failed,setFailed]=useState(false);
  useEffect(()=>{api<Profile>("/api/profile").then(setProfile).catch(()=>setFailed(true));},[]);
  const complete=profile && ["school","state","study_level","enrollment","assistance_categories"].every((key)=>profile.fields[key]);
  return <>
    <div className="page-heading"><div><p className="eyebrow">Your PathAid overview</p><h1>{complete?"Your support search starts here":"Complete your profile to find matches"}</h1><p>Recommendations use reviewed program information and transparent eligibility rules.</p></div></div>
    {failed?<section className="empty-panel"><h2>We could not load your profile</h2><p>Refresh the page or try again shortly.</p></section>:
    !profile?<section className="skeleton-panel" aria-label="Loading profile" />:
    !complete?<section className="empty-panel"><span className="step-badge">Next step</span><h2>Tell us the basics</h2><p>Add your school, study level, enrollment, and the support categories you want to explore.</p><Link className="button button-primary" href="/onboarding">Complete profile</Link></section>:
    <section className="dashboard-grid"><article className="metric-card"><span>Profile</span><strong>Ready</strong><p>Your core matching details are saved.</p></article><article className="metric-card"><span>Catalog</span><strong>Reviewed</strong><p>Only published opportunities appear.</p></article><article className="metric-card"><span>Eligibility</span><strong>Transparent</strong><p>Unknown answers remain clearly labeled.</p></article><div className="wide-card"><h2>Find current opportunities</h2><p>Review ranked results, missing information, evidence, and official application links.</p><Link className="button button-primary" href="/discover">Discover support</Link></div></section>}
  </>;
}
