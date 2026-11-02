"use client";

import { useEffect, useMemo, useState } from "react";
import { api, dateLabel } from "@/lib/api";
import type { SavedResponse, SavedScholarship, SavedStatus } from "@/types/api";

const tabs: { value: SavedStatus; label: string }[] = [
  { value: "not_started", label: "Not started" },
  { value: "in_progress", label: "In progress" },
  { value: "already_applied", label: "Already applied" },
];

export default function SavedPage() {
  const [items, setItems] = useState<SavedScholarship[]>([]);
  const [active, setActive] = useState<SavedStatus>("not_started");
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState("");
  const load = () => api<SavedResponse>("/api/saved-scholarships")
    .then(data => { setItems(data.items); setFailed(false); })
    .catch(() => setFailed(true));
  useEffect(() => { void load(); }, []);
  const visible = useMemo(() => items.filter(item => item.status === active), [items, active]);

  async function change(item: SavedScholarship, status: SavedStatus) {
    try {
      const updated = await api<SavedScholarship>(`/api/saved-scholarships/${item.scholarship_id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
      });
      setItems(current => current.map(entry => entry.scholarship_id === item.scholarship_id ? updated : entry));
      setMessage(`${item.name} moved to ${tabs.find(tab => tab.value === status)?.label}.`);
    } catch {
      setMessage(`${item.name} could not be updated.`);
    }
  }

  async function remove(item: SavedScholarship) {
    try {
      await api(`/api/saved-scholarships/${item.scholarship_id}`, { method: "DELETE" });
      setItems(current => current.filter(entry => entry.scholarship_id !== item.scholarship_id));
      setMessage(`${item.name} removed from Saved.`);
    } catch {
      setMessage(`${item.name} could not be removed.`);
    }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">Minimal application tracking</p><h1>Saved</h1><p>Keep only the status you need. PathAid does not track award decisions or submit applications.</p></div></div>
    <div className="saved-tabs" role="tablist" aria-label="Saved scholarship status">
      {tabs.map(tab => <button key={tab.value} role="tab" aria-selected={active === tab.value} onClick={() => setActive(tab.value)}>{tab.label}<span>{items.filter(item => item.status === tab.value).length}</span></button>)}
    </div>
    <p className="action-message" role="status" aria-live="polite">{message}</p>
    {failed && <section className="empty-panel"><h2>Saved scholarships unavailable</h2><p>Check that the local backend is running.</p><button className="button button-primary" onClick={load}>Try again</button></section>}
    {!failed && visible.length === 0 && <section className="empty-panel"><h2>No {tabs.find(tab => tab.value === active)?.label.toLowerCase()} scholarships</h2><p>Save a scholarship from Discover to add it here.</p></section>}
    <div className="saved-list">{visible.map(item => <article className="result-card" key={item.scholarship_id}>
      <header className="result-top"><p className="result-provider">{item.sponsor}</p><h2>{item.name}</h2></header>
      <dl className="result-facts"><div><dt>Award</dt><dd>{item.award ?? "Not stated"}</dd></div><div><dt>Deadline</dt><dd>{dateLabel(item.deadline)}</dd></div><div><dt>Source</dt><dd>{item.source_status === "active" && item.availability === "verified_open" ? "Current" : "Unavailable"}</dd></div></dl>
      <footer className="result-actions">
        <select aria-label={`Status for ${item.name}`} value={item.status} onChange={event => void change(item, event.target.value as SavedStatus)}>{tabs.map(tab => <option key={tab.value} value={tab.value}>{tab.label}</option>)}</select>
        <a className="button button-primary" href={item.application_url} target="_blank" rel="noreferrer" onClick={() => void change(item, "in_progress")}>Open application</a>
        <button className="text-action" onClick={() => void remove(item)}>Remove</button>
      </footer>
    </article>)}</div>
  </>;
}
