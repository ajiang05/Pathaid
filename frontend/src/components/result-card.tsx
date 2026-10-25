import Link from "next/link";
import { dateLabel, readable } from "@/lib/api";
import type { ProgramResult } from "@/types/api";

export function ResultCard({result}:{result:ProgramResult}) {
  return <article className="result-card">
    <header className="result-top"><p className="result-provider">{result.categories.map(readable).join(" · ")}</p><h3>{result.name}</h3></header>
    <p className="result-description">{result.description}</p>
    <dl className="result-facts"><div><dt>Amount</dt><dd>{result.assistance_amount??"Not verified"}</dd></div><div><dt>Deadline</dt><dd>{dateLabel(result.application_deadline)}</dd></div><div><dt>Availability</dt><dd>{readable(result.application_availability)}</dd></div></dl>
    <div className="pill-row"><span className={`status-pill status-${result.truth}`}>{result.label}</span></div>
    {result.missing_fields.length>0&&<p className="missing-note">Some eligibility details are not saved in your profile.</p>}
    <div className="result-footer"><span>{result.relevance&&readable(result.relevance)}</span><Link className="button button-primary" href={`/programs/${result.program_id}`}>View details</Link></div>
  </article>;
}
