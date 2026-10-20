"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, dateLabel, readable } from "@/lib/api";
import type { Evaluation, ProgramResult } from "@/types/api";

type Explanation={explanation:string;generated_by:string;fallback_reason?:string|null};
function text(item:Record<string,unknown>,...keys:string[]){for(const key of keys){if(typeof item[key]==="string")return item[key] as string}return "Reviewed requirement"}

export default function ProgramPage(){
  const {id}=useParams<{id:string}>();const [result,setResult]=useState<ProgramResult|null>(null);const [state,setState]=useState<"loading"|"ready"|"missing"|"error">("loading");const [explanation,setExplanation]=useState<Explanation|null>(null);const [explainPending,setExplainPending]=useState(false);
  useEffect(()=>{api<Evaluation>("/api/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers:{},categories:[]})}).then(data=>{const found=data.results.find(item=>item.program_id===id);if(found){setResult(found);setState("ready")}else setState("missing")}).catch(()=>setState("error"))},[id]);
  async function explain(){if(!result)return;setExplainPending(true);try{setExplanation(await api<Explanation>(`/api/programs/${id}/recommendation-explanation`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision_id:result.revision_id,answers:{}})}))}finally{setExplainPending(false)}}
  if(state==="loading")return <section className="skeleton-panel" aria-label="Loading program"/>;
  if(state==="missing")return <section className="empty-panel"><h1>This opportunity is not in your current results</h1><p>It may be outside your selected categories or reviewed coverage.</p></section>;
  if(state==="error"||!result)return <section className="empty-panel"><h1>Program unavailable</h1><p>We could not load this reviewed opportunity.</p></section>;
  return <>
    <article className="program-hero"><div className="verified-line">Reviewed source · Verified {dateLabel(result.verified_at)}</div><h1>{result.name}</h1><p>{result.description}</p><div className="program-facts"><div><span>Award amount</span><strong>{result.assistance_amount??"Not verified"}</strong></div><div><span>Application deadline</span><strong>{dateLabel(result.application_deadline)}</strong></div><div><span>Eligibility to apply</span><strong>{result.label}</strong></div></div><a className="button button-primary" href={result.application_url??result.provider_url} target="_blank" rel="noopener noreferrer">Open official provider site</a></article>
    <div className="detail-grid"><div className="detail-main">
      <section className="detail-card recommendation-card"><p className="eyebrow">Why this appears for you</p><p>{explanation?.explanation??result.template_explanation}</p><button className="button button-outline" disabled={explainPending} onClick={()=>void explain()}>{explainPending?"Preparing…":explanation?"Refresh explanation":"Get optional explanation"}</button>{explanation&&<small>{explanation.generated_by==="template"?"Template explanation":"AI-assisted wording from reviewed reasons"}</small>}</section>
      <section className="detail-card"><h2>Reviewed eligibility requirements</h2><div className="criteria-list">{result.criteria.map(c=><article key={c.id}><span className={`truth-mark truth-${c.truth}`} aria-label={readable(c.truth)}>{c.truth==="true"?"✓":c.truth==="false"?"×":"?"}</span><div><h3>{readable(c.field)}</h3><p>{c.reason}</p>{c.evidence.quote&&<blockquote>“{c.evidence.quote}”</blockquote>}</div></article>)}</div>{result.unresolved_conditions.length>0&&<div className="notice"><strong>Provider confirmation needed</strong><ul>{result.unresolved_conditions.map(item=><li key={item}>{item}</li>)}</ul></div>}</section>
      <section className="detail-card"><h2>Application materials</h2>{result.checklist.length?<div className="materials-grid">{result.checklist.map((item,index)=><article key={index}><h3>{text(item,"item","name","title","label")}</h3><p>{text(item,"description","details","evidence")}</p></article>)}</div>:<p>Application materials have not been verified. Confirm them with the provider.</p>}</section>
      {result.selection_factors.length>0&&<section className="detail-card"><h2>Selection factors</h2><p>These may affect award selection, but they do not change eligibility to apply.</p><ul>{result.selection_factors.map((item,index)=><li key={index}>{text(item,"factor","name","description","title")}</li>)}</ul></section>}
    </div><aside className="detail-aside"><section className="detail-card"><h2>Official sources</h2>{result.sources.map((source,index)=>{const url=String(source.source_url??result.provider_url);return <a className="source-link" key={index} href={url} target="_blank" rel="noopener noreferrer">Provider source <span aria-hidden="true">↗</span></a>})}</section><section className="detail-card trust-note"><h2>Important notice</h2><p>PathAid helps you understand requirements. The provider makes all final application and award decisions.</p></section></aside></div>
  </>;
}
