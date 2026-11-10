"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, readable } from "@/lib/api";
import type { Institution, InstitutionSelection, ManualLead, Profile, SourceScope, SourceSuggestion } from "@/types/api";

export default function SourcesPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [sources, setSources] = useState<SourceScope[]>([]);
  const [leads, setLeads] = useState<ManualLead[]>([]);
  const [schools, setSchools] = useState<Institution[]>([]);
  const [schoolQuery, setSchoolQuery] = useState("");
  const [sourceSuggestions, setSourceSuggestions] = useState<SourceSuggestion[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [scope, setScope] = useState({ name: "", ownership: "school", adapter: "generic", canonical_url: "", allowed_path_prefix: "/", max_depth: 1, page_budget: 25, requests_per_minute: 10, scan_interval_hours: 24 });
  const [lead, setLead] = useState({ title: "", url: "" });
  const [officialUrls, setOfficialUrls] = useState<Record<string, string>>({});
  const [policyInputs, setPolicyInputs] = useState<Record<string, { outcome: "allowed" | "blocked"; evidence_url: string; evidence_excerpt: string }>>({});

  const load = useCallback(async () => {
    try {
      const [nextProfile, nextSources, nextLeads] = await Promise.all([api<Profile>("/api/profile"), api<SourceScope[]>("/api/sources"), api<ManualLead[]>("/api/leads")]);
      setProfile(nextProfile); setSources(nextSources); setLeads(nextLeads); setError("");
    } catch { setError("Source registry unavailable. Check that the local backend is running."); }
  }, []);
  useEffect(() => {
    Promise.all([api<Profile>("/api/profile"), api<SourceScope[]>("/api/sources"), api<ManualLead[]>("/api/leads")])
      .then(([nextProfile, nextSources, nextLeads]) => { setProfile(nextProfile); setSources(nextSources); setLeads(nextLeads); })
      .catch(() => setError("Source registry unavailable. Check that the local backend is running."));
  }, []);

  function report(caught: unknown) {
    setMessage("");
    setError(caught instanceof ApiError ? caught.message : "The action could not be completed.");
  }

  async function searchSchool(event: FormEvent) {
    event.preventDefault();
    try { setSchools(await api<Institution[]>(`/api/institutions?q=${encodeURIComponent(schoolQuery)}`)); setError(""); }
    catch (caught) { report(caught); }
  }

  async function selectSchool(item: Institution) {
    try {
      const selected = await api<InstitutionSelection>(`/api/institutions/${item.unit_id}/select`, { method: "POST" });
      setSourceSuggestions(selected.source_suggestions);
      setMessage(`${item.name} is now your current school. Review a suggested directory or enter another official URL.`);
      setSchools([]); setSchoolQuery(""); await load();
    } catch (caught) { report(caught); }
  }

  function selectSuggestion(suggestion: SourceSuggestion) {
    setScope(current => ({
      ...current, name: suggestion.name, ownership: "school", adapter: suggestion.adapter,
      canonical_url: suggestion.canonical_url, allowed_path_prefix: suggestion.allowed_path_prefix,
    }));
    document.getElementById("source-proposal")?.scrollIntoView({ behavior: "smooth" });
  }

  async function proposeScope(event: FormEvent) {
    event.preventDefault();
    const schoolId = typeof profile?.fields.school_id === "string" ? profile.fields.school_id : null;
    try {
      await api<SourceScope>("/api/sources", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...scope, institution_unit_id: scope.ownership === "school" ? schoolId : null }) });
      setScope(current => ({ ...current, name: "", canonical_url: "", allowed_path_prefix: "/" }));
      setMessage("Source proposal saved. Review its exact host and path before confirming it."); await load();
    } catch (caught) { report(caught); }
  }

  async function sourceAction(item: SourceScope, action: "confirm" | "pause" | "resume" | "scan-now") {
    try {
      await api(`/api/sources/${item.id}/${action}`, { method: "POST" });
      setMessage(action === "scan-now" ? "The source is queued for its next scan." : `Source ${action === "confirm" ? "confirmed" : `${action}d`}.`);
      await load();
    } catch (caught) { report(caught); }
  }

  async function reviewPolicy(item: SourceScope) {
    const input = policyInputs[item.id] ?? { outcome: "allowed", evidence_url: "", evidence_excerpt: "" };
    try {
      await api(`/api/sources/${item.id}/policy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome: input.outcome, evidence_url: input.evidence_url || null, evidence_excerpt: input.evidence_excerpt || null }) });
      setMessage(input.outcome === "blocked" ? "Automation prohibition recorded. This source cannot scan." : "Policy review recorded. Scanning is allowed by the current decision.");
      setError(""); await load();
    } catch (caught) { report(caught); }
  }

  async function addLead(event: FormEvent) {
    event.preventDefault();
    try {
      await api<ManualLead>("/api/leads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lead) });
      setLead({ title: "", url: "" }); setMessage("Lead saved as one URL. Its surrounding domain was not approved."); await load();
    } catch (caught) { report(caught); }
  }

  async function verifyLead(item: ManualLead) {
    const officialUrl = officialUrls[item.id]?.trim();
    if (!officialUrl) { setError("Enter the current official sponsor page before verifying."); return; }
    try {
      const verified = await api<ManualLead>(`/api/leads/${item.id}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ official_url: officialUrl }) });
      setMessage(verified.status === "official_verified" ? "Official sponsor evidence verified and saved." : "The page could not be verified as current official scholarship evidence.");
      setError(verified.last_error_code ? readable(verified.last_error_code) : "");
      await load();
    } catch (caught) { report(caught); }
  }

  const selectedSchool = typeof profile?.fields.school === "string" ? profile.fields.school : "No institution selected";
  const selectedSchoolId = typeof profile?.fields.school_id === "string" ? profile.fields.school_id : null;

  return <>
    <div className="page-heading"><div><p className="eyebrow">Explicit crawl permission</p><h1>Sources</h1><p>Confirm a precise host and path once. PathAid cannot scan outside that boundary, and individual leads never approve a whole website.</p></div></div>
    {message && <p className="form-success" role="status">{message}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}

    <section className="form-card source-section"><div className="form-card-heading"><p className="eyebrow">NCES IPEDS directory</p><h2>Current institution</h2></div>
      <p><strong>{selectedSchool}</strong>{selectedSchoolId && <> · Unit ID {selectedSchoolId}</>}</p>
      <form className="inline-form" onSubmit={searchSchool}><label>Find a U.S. college or university<input value={schoolQuery} minLength={2} required onChange={event => setSchoolQuery(event.target.value)} /></label><button className="button button-outline">Search</button></form>
      {schools.length > 0 && <div className="institution-results">{schools.map(item => <article key={item.unit_id}><div><strong>{item.name}</strong><span>{item.city}, {item.state} · NCES {item.source_year}</span></div><button className="button button-outline" onClick={() => selectSchool(item)}>Select</button></article>)}</div>}
    </section>

    <section className="form-card source-section" id="source-proposal"><div className="form-card-heading"><p className="eyebrow">Bounded automation</p><h2>Propose a directory</h2><p className="field-help">Saving is not approval. You must inspect and confirm the exact boundary before any scan can run.</p></div>
      {sourceSuggestions.length > 0 && <div className="suggestion-list" aria-label="Likely official directory paths"><p>Unverified paths on the school&apos;s official host:</p>{sourceSuggestions.map(suggestion => <button type="button" className="button button-outline" key={suggestion.canonical_url} onClick={() => selectSuggestion(suggestion)}>Use {suggestion.allowed_path_prefix}</button>)}</div>}
      <form className="source-form" onSubmit={proposeScope}>
        <label>Source name<input value={scope.name} required onChange={event => setScope({ ...scope, name: event.target.value })} /></label>
        <label>Ownership<select value={scope.ownership} onChange={event => setScope({ ...scope, ownership: event.target.value })}><option value="school">Current school</option><option value="sponsor">Scholarship sponsor</option></select></label>
        <label>Adapter<select value={scope.adapter} onChange={event => setScope({ ...scope, adapter: event.target.value, ownership: event.target.value === "kaleidoscope" ? "sponsor" : scope.ownership, allowed_path_prefix: ["academicworks", "kaleidoscope"].includes(event.target.value) ? "/" : scope.allowed_path_prefix })}><option value="generic">Generic directory</option><option value="academicworks">AcademicWorks / Blackbaud</option><option value="kaleidoscope">Kaleidoscope marketplace</option></select></label>
        <label className="full-field">Directory URL<input type="url" value={scope.canonical_url} required onChange={event => setScope({ ...scope, canonical_url: event.target.value })} /></label>
        <label className="full-field">Allowed path prefix<input value={scope.allowed_path_prefix} required onChange={event => setScope({ ...scope, allowed_path_prefix: event.target.value })} /><small>Example: /financialaid/scholarships. This never expands automatically.</small></label>
        <label>Maximum link depth<input type="number" min="0" max="2" value={scope.max_depth} onChange={event => setScope({ ...scope, max_depth: Number(event.target.value) })} /></label>
        <label>Page budget<input type="number" min="1" max="100" value={scope.page_budget} onChange={event => setScope({ ...scope, page_budget: Number(event.target.value) })} /></label>
        <label>Requests per minute<input type="number" min="1" max="60" value={scope.requests_per_minute} onChange={event => setScope({ ...scope, requests_per_minute: Number(event.target.value) })} /></label>
        <label>Scan interval (hours)<input type="number" min="6" max="720" value={scope.scan_interval_hours} onChange={event => setScope({ ...scope, scan_interval_hours: Number(event.target.value) })} /></label>
        <button className="button button-primary">Save unconfirmed proposal</button>
      </form>
    </section>

    <section className="source-section"><div className="section-heading"><h2>Registered boundaries</h2><span>{sources.length}</span></div>
      {sources.length === 0 ? <div className="empty-panel"><h3>No directory scopes</h3><p>Add a proposed source, then explicitly confirm it.</p></div> : <div className="source-list">{sources.map(item => { const policy = policyInputs[item.id] ?? { outcome: "allowed" as const, evidence_url: "", evidence_excerpt: "" }; return <article className="source-card" key={item.id}><div><div className="pill-row"><span className="info-pill">{readable(item.status)}</span><span className="info-pill">{readable(item.adapter)}</span><span className="info-pill">Policy: {readable(item.policy_status)}</span></div><h3>{item.name}</h3><p>{item.hostname}<strong>{item.allowed_path_prefix}</strong></p><dl><div><dt>Depth / pages</dt><dd>{item.max_depth} / {item.page_budget}</dd></div><div><dt>Rate</dt><dd>{item.requests_per_minute}/minute</dd></div><div><dt>Interval</dt><dd>{item.scan_interval_hours} hours</dd></div><div><dt>Next scan</dt><dd>{item.next_scan_at ? new Date(item.next_scan_at).toLocaleString() : "Not scheduled"}</dd></div></dl>{item.status !== "proposed" && item.status !== "inactive" && <div className="source-form"><label>Automation policy<select value={policy.outcome} onChange={event => setPolicyInputs({ ...policyInputs, [item.id]: { ...policy, outcome: event.target.value as "allowed" | "blocked" } })}><option value="allowed">No explicit prohibition found</option><option value="blocked">Automation explicitly prohibited</option></select></label><label>Official policy URL<input type="url" value={policy.evidence_url} onChange={event => setPolicyInputs({ ...policyInputs, [item.id]: { ...policy, evidence_url: event.target.value } })} /></label><label className="full-field">Exact policy text<textarea value={policy.evidence_excerpt} onChange={event => setPolicyInputs({ ...policyInputs, [item.id]: { ...policy, evidence_excerpt: event.target.value } })} /><small>Required when blocking automation. Do not paraphrase the prohibition.</small></label><button className="button button-outline" type="button" onClick={() => reviewPolicy(item)}>Record policy review</button></div>}</div><div className="row-actions">{item.status === "proposed" && <button className="button button-primary" onClick={() => sourceAction(item, "confirm")}>Confirm boundary</button>}{item.status === "active" && <><button className="button button-outline" disabled={item.policy_status !== "allowed"} onClick={() => sourceAction(item, "scan-now")}>Scan now</button><button className="button button-outline" onClick={() => sourceAction(item, "pause")}>Pause</button></>}{item.status === "paused" && <button className="button button-primary" disabled={item.policy_status !== "allowed"} onClick={() => sourceAction(item, "resume")}>Resume</button>}</div></article>; })}</div>}
    </section>

    <section className="form-card source-section"><div className="form-card-heading"><p className="eyebrow">No crawl permission</p><h2>Manual leads</h2><p className="field-help">Use this for BigFuture, Scholarship America, Bold.org, or any single URL you want verified later.</p></div>
      <form className="inline-form" onSubmit={addLead}><label>Lead title<input value={lead.title} required onChange={event => setLead({ ...lead, title: event.target.value })} /></label><label>Exact URL<input type="url" value={lead.url} required onChange={event => setLead({ ...lead, url: event.target.value })} /></label><button className="button button-outline">Save lead</button></form>
      {leads.length > 0 && <div className="lead-list">{leads.map(item => <article key={item.id}><div><strong>{item.title}</strong><span>{item.hostname} · {readable(item.status)}{item.verified_at ? ` · verified ${new Date(item.verified_at).toLocaleDateString()}` : ""}</span>{item.last_error_code && <span className="form-error">{readable(item.last_error_code)}</span>}<label>Official sponsor page<input type="url" placeholder="https://sponsor.org/scholarship" value={officialUrls[item.id] ?? item.official_url ?? ""} onChange={event => setOfficialUrls({ ...officialUrls, [item.id]: event.target.value })} /></label></div><div className="row-actions"><a className="text-link" href={item.canonical_url} target="_blank" rel="noreferrer">Open lead</a><button className="button button-outline" type="button" onClick={() => verifyLead(item)}>Verify official page</button>{item.official_url && <a className="text-link" href={item.official_url} target="_blank" rel="noreferrer">Open official page</a>}</div></article>)}</div>}
    </section>
  </>;
}
