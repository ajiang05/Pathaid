"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FeedbackToast } from "@/components/feedback-toast";
import type { DocumentsResponse, Essay, EssayAnalysisSettings, EssayRecommendationsResponse, EssaysResponse, ManagedDocument } from "@/types/api";

const documentTypes = [
  { type: "resume" as const, title: "Résumé", description: "Your one current résumé for applications that request it." },
  { type: "transcript" as const, title: "Transcript", description: "Your one current academic transcript." },
];

function sizeLabel(bytes: number) {
  return `${(bytes / 1024).toFixed(bytes < 1024 * 10 ? 1 : 0)} KB`;
}

export default function DocumentsPage() {
  const [items, setItems] = useState<ManagedDocument[]>([]);
  const [files, setFiles] = useState<Partial<Record<ManagedDocument["document_type"], File>>>({});
  const [busy, setBusy] = useState<ManagedDocument["document_type"] | null>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [essays, setEssays] = useState<Essay[]>([]);
  const [essayDraft, setEssayDraft] = useState({ title: "", original_prompt: "", text: "", tags: "", themes: "", written_on: new Date().toISOString().slice(0, 10) });
  const [editingEssayId, setEditingEssayId] = useState<string | null>(null);
  const [destination, setDestination] = useState({ prompt: "", word_limit: "" });
  const [recommendations, setRecommendations] = useState<EssayRecommendationsResponse | null>(null);
  const [analysis, setAnalysis] = useState<EssayAnalysisSettings | null>(null);

  const load = () => api<DocumentsResponse>("/api/documents")
    .then(data => { setItems(data.items); setFailed(false); })
    .catch(() => setFailed(true));
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    void Promise.all([
      api<EssaysResponse>("/api/essays").then(data => setEssays(data.items)),
      api<EssayAnalysisSettings>("/api/essays/analysis-settings").then(setAnalysis),
    ]).catch(() => setMessage("The essay bank could not be loaded."));
  }, []);

  async function upload(documentType: ManagedDocument["document_type"]) {
    const file = files[documentType];
    if (!file) { setMessage("Choose a PDF before uploading."); return; }
    setBusy(documentType); setMessage("");
    try {
      const saved = await api<ManagedDocument>(`/api/documents/${documentType}`, {
        method: "PUT",
        headers: { "Content-Type": file.type || "application/pdf", "X-PathAid-Filename": encodeURIComponent(file.name) },
        body: file,
      });
      setItems(current => [...current.filter(item => item.document_type !== documentType), saved]);
      setFiles(current => ({ ...current, [documentType]: undefined }));
      setMessage(`${documentType === "resume" ? "Résumé" : "Transcript"} encrypted and stored locally.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The document could not be stored.");
    } finally { setBusy(null); }
  }

  async function remove(document: ManagedDocument) {
    if (!window.confirm(`Remove the stored ${document.document_type}?`)) return;
    setBusy(document.document_type); setMessage("");
    try {
      await api(`/api/documents/${document.document_type}`, { method: "DELETE" });
      setItems(current => current.filter(item => item.document_type !== document.document_type));
      setMessage("Encrypted document removed.");
    } catch { setMessage("The document could not be removed."); }
    finally { setBusy(null); }
  }

  function labels(value: string) {
    return value.split(",").map(item => item.trim()).filter(Boolean);
  }

  async function saveEssay() {
    setMessage("");
    const payload = { ...essayDraft, tags: labels(essayDraft.tags), themes: labels(essayDraft.themes) };
    try {
      const saved = await api<Essay>(editingEssayId ? `/api/essays/items/${editingEssayId}` : "/api/essays", {
        method: editingEssayId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      setEssays(current => [saved, ...current.filter(item => item.id !== saved.id)]);
      setEssayDraft({ title: "", original_prompt: "", text: "", tags: "", themes: "", written_on: new Date().toISOString().slice(0, 10) });
      setEditingEssayId(null);
      setMessage("Student-written essay saved locally.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "The essay could not be saved."); }
  }

  function editEssay(essay: Essay) {
    setEditingEssayId(essay.id);
    setEssayDraft({ title: essay.title, original_prompt: essay.original_prompt, text: essay.text, tags: essay.tags.join(", "), themes: essay.themes.join(", "), written_on: essay.written_on });
    document.getElementById("essay-editor")?.scrollIntoView({ behavior: "smooth" });
  }

  async function removeEssay(essay: Essay) {
    if (!window.confirm(`Remove “${essay.title}” and its local use history?`)) return;
    await api(`/api/essays/items/${essay.id}`, { method: "DELETE" });
    setEssays(current => current.filter(item => item.id !== essay.id));
    setMessage("Essay removed.");
  }

  async function saveAnalysisSettings(next: EssayAnalysisSettings) {
    const saved = await api<EssayAnalysisSettings>("/api/essays/analysis-settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_text_analysis_enabled: next.full_text_analysis_enabled, data_tier: next.data_tier, notice_acknowledged: next.notice_acknowledged }),
    });
    setAnalysis(saved); setMessage("Essay-analysis settings saved.");
  }

  async function recommend(useGemini: boolean) {
    if (!destination.prompt.trim()) { setMessage("Enter the scholarship essay prompt first."); return; }
    try {
      const result = await api<EssayRecommendationsResponse>("/api/essays/recommendations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ destination_prompt: destination.prompt, word_limit: destination.word_limit ? Number(destination.word_limit) : null, use_gemini: useGemini }),
      });
      setRecommendations(result); setMessage(result.warning ?? `${result.source === "gemini" ? "Gemini" : "Local"} recommendations ready.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Recommendations could not be prepared."); }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">Private application library</p><h1>Documents and essays</h1><p>Store your current documents and your own writing locally. PathAid recommends existing essays but never generates or rewrites them.</p></div></div>
    <FeedbackToast message={message} tone="info" onDismiss={() => setMessage("")} />
    {failed && <section className="empty-panel"><h2>Document vault unavailable</h2><p>Check that the local backend and macOS Keychain are available.</p><button className="button button-primary" onClick={load}>Try again</button></section>}
    {!failed && <div className="document-grid">{documentTypes.map(spec => {
      const stored = items.find(item => item.document_type === spec.type);
      return <section className="form-card" key={spec.type}>
        <div className="form-card-heading"><p className="eyebrow">Managed PDF</p><h2>{spec.title}</h2><p>{spec.description}</p></div>
        {stored ? <dl className="document-metadata"><div><dt>File</dt><dd>{stored.original_name}</dd></div><div><dt>Size</dt><dd>{sizeLabel(stored.size_bytes)}</dd></div><div><dt>Updated</dt><dd>{new Date(stored.updated_at).toLocaleString()}</dd></div></dl> : <p>No {spec.title.toLowerCase()} stored.</p>}
        <div className="field-row"><label htmlFor={`${spec.type}-file`}>{stored ? "Replace PDF" : "Choose PDF"}</label><input id={`${spec.type}-file`} type="file" accept="application/pdf,.pdf" onChange={event => setFiles(current => ({ ...current, [spec.type]: event.target.files?.[0] }))} /></div>
        <div className="result-actions"><button className="button button-primary" disabled={busy !== null || !files[spec.type]} onClick={() => void upload(spec.type)}>{busy === spec.type ? "Encrypting…" : stored ? "Replace encrypted copy" : "Encrypt and store"}</button>{stored && <button className="text-action" disabled={busy !== null} onClick={() => void remove(stored)}>Remove</button>}</div>
      </section>;
    })}</div>}

    <section className="form-card" id="essay-editor">
      <div className="form-card-heading"><p className="eyebrow">Student-written only</p><h2>{editingEssayId ? "Edit essay" : "Add an essay"}</h2><p>Tags and themes power local matching before any optional Gemini analysis.</p></div>
      <div className="field-row"><label htmlFor="essay-title">Title</label><input id="essay-title" value={essayDraft.title} onChange={event => setEssayDraft(current => ({ ...current, title: event.target.value }))} /></div>
      <div className="field-row"><label htmlFor="essay-original-prompt">Original prompt</label><textarea id="essay-original-prompt" value={essayDraft.original_prompt} onChange={event => setEssayDraft(current => ({ ...current, original_prompt: event.target.value }))} /></div>
      <div className="field-row"><label htmlFor="essay-text">Your essay</label><textarea id="essay-text" rows={12} value={essayDraft.text} onChange={event => setEssayDraft(current => ({ ...current, text: event.target.value }))} /></div>
      <div className="form-grid"><div className="field-row"><label htmlFor="essay-tags">Tags, comma separated</label><input id="essay-tags" value={essayDraft.tags} onChange={event => setEssayDraft(current => ({ ...current, tags: event.target.value }))} /></div><div className="field-row"><label htmlFor="essay-themes">Themes, comma separated</label><input id="essay-themes" value={essayDraft.themes} onChange={event => setEssayDraft(current => ({ ...current, themes: event.target.value }))} /></div><div className="field-row"><label htmlFor="essay-date">Date written</label><input id="essay-date" type="date" value={essayDraft.written_on} onChange={event => setEssayDraft(current => ({ ...current, written_on: event.target.value }))} /></div></div>
      <div className="result-actions"><button className="button button-primary" onClick={() => void saveEssay()}>{editingEssayId ? "Save changes" : "Add to essay bank"}</button>{editingEssayId && <button className="text-action" onClick={() => setEditingEssayId(null)}>Cancel</button>}</div>
    </section>

    <section className="form-card">
      <div className="form-card-heading"><p className="eyebrow">Local-first matching</p><h2>Find an essay for a new prompt</h2><p>Your full essay text is sent to Gemini only when the setting below is enabled and you explicitly choose Gemini analysis.</p></div>
      <div className="field-row"><label htmlFor="destination-prompt">Scholarship essay prompt</label><textarea id="destination-prompt" value={destination.prompt} onChange={event => setDestination(current => ({ ...current, prompt: event.target.value }))} /></div>
      <div className="field-row"><label htmlFor="destination-limit">Word limit (optional)</label><input id="destination-limit" type="number" min="1" value={destination.word_limit} onChange={event => setDestination(current => ({ ...current, word_limit: event.target.value }))} /></div>
      <div className="result-actions"><button className="button button-primary" onClick={() => void recommend(false)}>Match locally</button><button className="button" disabled={!analysis?.full_text_analysis_enabled || !analysis.notice_acknowledged || analysis.data_tier === "unknown" || !analysis.gemini_key_configured} onClick={() => void recommend(true)}>Analyze with Gemini</button></div>
      {recommendations && <div className="document-grid" aria-live="polite">{recommendations.items.map(item => { const essay = essays.find(candidate => candidate.id === item.essay_id); return <article className="result-card" key={item.essay_id}><p className="eyebrow">{recommendations.source} recommendation</p><h3>{essay?.title ?? "Essay"}</h3><p>{item.rationale}</p>{item.warnings.map(warning => <p className="inline-warning" key={warning}>{warning}</p>)}{item.mismatches.map(mismatch => <p key={`${mismatch.section_reference}-${mismatch.reason}`}><strong>{mismatch.section_reference}:</strong> {mismatch.reason}</p>)}</article>; })}</div>}
    </section>

    {analysis && <section className="form-card">
      <div className="form-card-heading"><p className="eyebrow">Explicit AI configuration</p><h2>Gemini full-text analysis</h2><p>{analysis.notice} PathAid does not log full essays or model responses.</p></div>
      <div className="field-row"><label htmlFor="gemini-tier">Configured Gemini account tier</label><select id="gemini-tier" value={analysis.data_tier} onChange={event => setAnalysis(current => current && ({ ...current, data_tier: event.target.value as EssayAnalysisSettings["data_tier"] }))}><option value="unknown">I am not sure</option><option value="unpaid">Unpaid / free tier</option><option value="paid">Paid tier</option></select></div>
      <label className="check-row"><input type="checkbox" checked={analysis.notice_acknowledged} onChange={event => setAnalysis(current => current && ({ ...current, notice_acknowledged: event.target.checked }))} /><span>I understand that the complete essay and destination prompt leave my Mac when Gemini analysis runs.</span></label>
      <label className="check-row"><input type="checkbox" checked={analysis.full_text_analysis_enabled} onChange={event => setAnalysis(current => current && ({ ...current, full_text_analysis_enabled: event.target.checked }))} /><span>Enable optional full-text Gemini analysis</span></label>
      <p>Gemini key: {analysis.gemini_key_configured ? "configured in macOS Keychain" : "not configured"}</p>
      <button className="button button-primary" onClick={() => void saveAnalysisSettings(analysis)}>Save analysis settings</button>
    </section>}

    <section className="form-card"><div className="form-card-heading"><p className="eyebrow">Local essay bank</p><h2>Your essays</h2></div>{essays.length === 0 ? <p>No essays saved yet.</p> : <div className="document-grid">{essays.map(essay => <article className="result-card" key={essay.id}><h3>{essay.title}</h3><p>{essay.word_count} words · written {new Date(`${essay.written_on}T00:00:00`).toLocaleDateString()} · used {essay.uses.length} times</p><p>{[...essay.tags, ...essay.themes].join(" · ") || "No tags yet"}</p><div className="result-actions"><button className="button" onClick={() => editEssay(essay)}>Edit</button><button className="text-action" onClick={() => void removeEssay(essay)}>Remove</button></div></article>)}</div>}</section>
  </>;
}
