"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SettingsStatus } from "@/types/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [geminiKey, setGeminiKey] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api<SettingsStatus>("/api/settings/status")
    .then(setStatus)
    .catch(() => setMessage("Local settings are unavailable. Check that the backend is running."));
  useEffect(() => { void load(); }, []);

  async function saveGeminiKey() {
    if (geminiKey.trim().length < 8) { setMessage("Enter a valid Gemini API key."); return; }
    setBusy(true); setMessage("");
    try {
      await api("/api/settings/gemini-key", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: geminiKey.trim() }),
      });
      setGeminiKey(""); setMessage("Gemini key saved in macOS Keychain."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "The Gemini key could not be saved."); }
    finally { setBusy(false); }
  }

  async function downloadBackup() {
    if (passphrase.length < 12) { setMessage("Use a backup passphrase of at least 12 characters."); return; }
    if (passphrase !== confirmation) { setMessage("Backup passphrases do not match."); return; }
    setBusy(true); setMessage("");
    try {
      const response = await fetch("/api/settings/backup", {
        method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passphrase }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(typeof payload?.detail === "string" ? payload.detail : "Backup could not be created.");
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] || "pathaid.pathaid-backup";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = filename; link.click();
      URL.revokeObjectURL(url);
      setPassphrase(""); setConfirmation("");
      setMessage("Encrypted backup downloaded. Keep its passphrase somewhere separate and safe.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Backup could not be created."); }
    finally { setBusy(false); }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">Local configuration</p><h1>Settings</h1><p>Manage Keychain-backed AI access, extension pairing, encrypted backups, and destructive recovery commands.</p></div></div>
    <p className="action-message" role="status" aria-live="polite">{message}</p>

    <div className="document-grid">
      <section className="form-card">
        <div className="form-card-heading"><p className="eyebrow">macOS Keychain</p><h2>Gemini API key</h2><p>The key is stored in Keychain, never SQLite or a backup.</p></div>
        <p>Status: <strong>{status?.gemini_configured ? "Configured" : "Not configured"}</strong></p>
        <div className="field-row"><label htmlFor="gemini-api-key">New Gemini API key</label><input id="gemini-api-key" type="password" autoComplete="off" value={geminiKey} onChange={event => setGeminiKey(event.target.value)} /></div>
        <button className="button button-primary" disabled={busy || !geminiKey} onClick={() => void saveGeminiKey()}>Save key in Keychain</button>
      </section>

      <section className="form-card">
        <div className="form-card-heading"><p className="eyebrow">Chrome developer mode</p><h2>Application copilot</h2><p>Load the repository&apos;s extension folder unpacked, then pair it with the installation token.</p></div>
        <dl className="document-metadata"><div><dt>Extension ID</dt><dd>{status?.extension_configured ? status.extension_id : "Not configured"}</dd></div><div><dt>Installation token</dt><dd>{status?.extension_token_available ? "Available in Keychain" : "Missing"}</dd></div></dl>
        <pre><code>scripts/pathaid configure-extension EXTENSION_ID{"\n"}scripts/pathaid copy-extension-token</code></pre>
      </section>
    </div>

    <section className="form-card">
      <div className="form-card-heading"><p className="eyebrow">Portable recovery</p><h2>Encrypted backup</h2><p>Creates a consistent {status?.backup_format ?? "encrypted"} archive. PathAid does not store the passphrase and cannot recover it.</p></div>
      <div className="form-grid"><div className="field-row"><label htmlFor="backup-passphrase">Backup passphrase</label><input id="backup-passphrase" type="password" autoComplete="new-password" value={passphrase} onChange={event => setPassphrase(event.target.value)} /></div><div className="field-row"><label htmlFor="backup-confirmation">Confirm passphrase</label><input id="backup-confirmation" type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} /></div></div>
      <button className="button button-primary" disabled={busy || !passphrase || !confirmation} onClick={() => void downloadBackup()}>Download encrypted backup</button>
      <h3>Always excluded</h3><ul>{status?.backup_excludes.map(item => <li key={item}>{item}</li>)}</ul>
    </section>

    <section className="form-card">
      <div className="form-card-heading"><p className="eyebrow">Stopped-process recovery</p><h2>Restore or factory reset</h2><p>These operations replace or remove live data, so they intentionally run in Terminal after PathAid stops.</p></div>
      <pre><code>scripts/pathaid stop{"\n"}scripts/pathaid restore /absolute/path/backup.pathaid-backup</code></pre>
      <pre><code>scripts/pathaid reset</code></pre>
      <p>Reset removes only PathAid SQLite, managed encrypted documents, and PathAid Keychain entries. Review <Link href="/privacy">privacy and safety</Link> before enabling full-essay Gemini analysis.</p>
    </section>
  </>;
}
