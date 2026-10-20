import Link from "next/link";
import { dateLabel, readable } from "@/lib/api";
import type { ProgramResult } from "@/types/api";

export function ResultCard({result}:{result:ProgramResult}) {
  return <article className="result-card">
    <div className="result-top"><div><p className="result-provider">{result.categories.map(readable).join(" · ")}</p><h3>{result.name}</h3></div><strong className="result-amount">{result.assistance_amount??"Amount not verified"}</strong></div>
    <p>{result.description}</p>
    <div className="pill-row"><span className={`status-pill status-${result.truth}`}>{result.label}</span><span className="info-pill">Deadline: {dateLabel(result.application_deadline)}</span><span className="info-pill">{readable(result.application_availability)}</span></div>
    {result.missing_fields.length>0&&<p className="missing-note">Needs {result.missing_fields.length} more {result.missing_fields.length===1?"answer":"answers"} for a clearer result.</p>}
    <div className="result-footer"><span>{result.relevance&&readable(result.relevance)}</span><Link className="button button-primary" href={`/programs/${result.program_id}`}>View details</Link></div>
  </article>;
}
