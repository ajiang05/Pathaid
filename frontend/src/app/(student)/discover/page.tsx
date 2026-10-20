"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, readable } from "@/lib/api";
import type { Evaluation, MissingField, ProfileFields, ProgramResult } from "@/types/api";
import { ResultCard } from "@/components/result-card";

const sectionOrder=["Open opportunities","Confirm availability","Closed opportunities"];

function FollowUp({field,value,onChange}:{field:MissingField;value:ProfileFields[string];onChange:(v:ProfileFields[string])=>void}) {
  if(field.answer_type==="choice")return <select value={typeof value==="string"?value:""} onChange={e=>onChange(e.target.value||null)}><option value="">I don&apos;t know</option>{field.values?.map(v=><option key={String(v)} value={String(v)}>{readable(String(v))}</option>)}</select>;
  if(field.answer_type==="boolean")return <select value={typeof value==="boolean"?String(value):""} onChange={e=>onChange(e.target.value===""?null:e.target.value==="true")}><option value="">I don&apos;t know</option><option value="true">Yes</option><option value="false">No</option></select>;
  return <input type={field.answer_type==="number"||field.answer_type==="integer"?"number":"text"} value={typeof value==="string"||typeof value==="number"?value:""} onChange={e=>onChange(e.target.value===""?null:field.answer_type==="number"?Number(e.target.value):field.answer_type==="integer"?Number.parseInt(e.target.value,10):e.target.value)}/>;
}

export default function DiscoverPage(){
  const [evaluation,setEvaluation]=useState<Evaluation|null>(null);const [answers,setAnswers]=useState<ProfileFields>({});const [state,setState]=useState<"loading"|"ready"|"empty"|"error">("loading");const [message,setMessage]=useState("");
  const evaluate=useCallback(async(next:ProfileFields={})=>{setState("loading");try{const data=await api<Evaluation>("/api/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers:next,categories:[]})});setEvaluation(data);setState(data.results.length?"ready":"empty")}catch(error){setState("error");setMessage(error instanceof ApiError&&error.status===422?"Complete your core profile and choose at least one support category first.":"We could not evaluate the catalog. Try again shortly.")}},[]);
  useEffect(()=>{const timer=window.setTimeout(()=>void evaluate({}),0);return()=>window.clearTimeout(timer)},[evaluate]);
  const missing=useMemo(()=>{const map=new Map<string,MissingField>();evaluation?.results.flatMap(r=>r.missing_fields).forEach(f=>map.set(f.field,f));return [...map.values()]},[evaluation]);
  const grouped=useMemo(()=>{const groups=new Map<string,ProgramResult[]>();evaluation?.results.forEach(r=>{const key=r.availability_section??"open";groups.set(key,[...(groups.get(key)??[]),r])});return groups},[evaluation]);
  return <><div className="page-heading"><div><p className="eyebrow">Reviewed catalog</p><h1>Discover support</h1><p>Results are grouped by eligibility and availability using your saved profile.</p></div></div>
    {state==="loading"&&<section className="skeleton-panel" aria-label="Evaluating opportunities"/>}
    {state==="error"&&<section className="empty-panel"><h2>Recommendations unavailable</h2><p>{message}</p><button className="button button-primary" onClick={()=>void evaluate(answers)}>Try again</button></section>}
    {state==="empty"&&<section className="empty-panel"><h2>No reviewed programs match these categories yet</h2><p>This reflects the current catalog coverage, not your eligibility for financial support.</p></section>}
    {state==="ready"&&<div className="results-layout">
      {missing.length>0&&<aside className="followup-panel"><p className="eyebrow">Optional follow-up</p><h2>Clarify your results</h2><p>These answers are used for this evaluation only unless you later save them to your profile.</p>{missing.map(f=><div className="field-row" key={f.field}><label>{f.question}</label><FollowUp field={f} value={answers[f.field]} onChange={v=>setAnswers(a=>({...a,[f.field]:v}))}/>{f.sensitive&&<p className="field-help">Sensitive and optional. Choose “I don&apos;t know” to skip.</p>}</div>)}<button className="button button-primary" onClick={()=>void evaluate(answers)}>Update results</button></aside>}
      <div className="results-list">{sectionOrder.filter(s=>grouped.has(s)).map((section,index)=><section key={section} aria-labelledby={`results-section-${index}`}><div className="section-heading"><h2 id={`results-section-${index}`}>{section}</h2><span>{grouped.get(section)?.length}</span></div>{grouped.get(section)?.map(result=><ResultCard key={result.program_id} result={result}/>)}</section>)}</div>
    </div>}
  </>;
}
