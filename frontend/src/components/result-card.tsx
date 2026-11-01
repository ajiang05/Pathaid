import { readable } from "@/lib/api";
import type { MatchResult } from "@/types/api";

function deadline(value: string | null) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(value));
}

export function ResultCard({ result }: { result: MatchResult }) {
  const statusClass = result.match_label === "Strong match" ? "status-true" : "status-pill";
  return <article className="result-card">
    <header className="result-top"><p className="result-provider">{result.sponsor}</p><h3>{result.name}</h3></header>
    <dl className="result-facts"><div><dt>Award</dt><dd>{result.award ?? "Not stated"}</dd></div><div><dt>Deadline</dt><dd>{deadline(result.deadline)}</dd></div><div><dt>Eligibility</dt><dd>{result.match_label}</dd></div></dl>
    <div className="pill-row"><span className={`status-pill ${statusClass}`}>{result.match_label}</span></div>
    {result.key_reasons.length > 0 && <ul className="missing-note">{result.key_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
    {result.unknown_fields.length > 0 && <p className="missing-note">Unknown: {result.unknown_fields.map(readable).join(", ")}</p>}
  </article>;
}
