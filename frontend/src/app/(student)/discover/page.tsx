"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Evaluation, ProgramResult } from "@/types/api";
import { ResultCard } from "@/components/result-card";

const sectionOrder=["Open opportunities","Confirm availability","Closed opportunities"];

export default function DiscoverPage(){
  const [evaluation,setEvaluation]=useState<Evaluation|null>(null);const [state,setState]=useState<"loading"|"ready"|"empty"|"error">("loading");const [message,setMessage]=useState("");
  const evaluate=useCallback(async()=>{setState("loading");try{const data=await api<Evaluation>("/api/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers:{},categories:[]})});setEvaluation(data);setState(data.results.length?"ready":"empty")}catch(error){setState("error");setMessage(error instanceof ApiError&&error.status===422?"Complete your core profile and choose at least one support category first.":"We could not evaluate the catalog. Try again shortly.")}},[]);
  useEffect(()=>{const timer=window.setTimeout(()=>void evaluate(),0);return()=>window.clearTimeout(timer)},[evaluate]);
  const hasMissingProfileDetails=useMemo(()=>evaluation?.results.some(result=>result.missing_fields.length>0)??false,[evaluation]);
  const grouped=useMemo(()=>{const groups=new Map<string,ProgramResult[]>();evaluation?.results.forEach(r=>{const key=r.availability_section??"open";groups.set(key,[...(groups.get(key)??[]),r])});return groups},[evaluation]);
  return <><div className="page-heading"><div><p className="eyebrow">Reviewed catalog</p><h1>Discover support</h1><p>Results are grouped by eligibility and availability using your saved profile.</p></div></div>
    {state==="loading"&&<section className="skeleton-panel" aria-label="Evaluating opportunities"/>}
    {state==="error"&&<section className="empty-panel"><h2>Recommendations unavailable</h2><p>{message}</p><button className="button button-primary" onClick={()=>void evaluate()}>Try again</button></section>}
    {state==="empty"&&<section className="empty-panel"><h2>No reviewed programs match these categories yet</h2><p>This reflects the current catalog coverage, not your eligibility for financial support.</p></section>}
    {state==="ready"&&<div className="results-layout">
      {hasMissingProfileDetails&&<section className="profile-details-note"><div><strong>Want more precise eligibility results?</strong><p>Add any optional details you are comfortable sharing in your student profile.</p></div><Link className="button button-outline" href="/profile">Update profile</Link></section>}
      <div className="results-list">{sectionOrder.filter(s=>grouped.has(s)).map((section,index)=><section key={section} aria-labelledby={`results-section-${index}`}><div className="section-heading"><h2 id={`results-section-${index}`}>{section}</h2><span>{grouped.get(section)?.length}</span></div><div className="result-grid">{grouped.get(section)?.map(result=><ResultCard key={result.program_id} result={result}/>)}</div></section>)}</div>
    </div>}
  </>;
}
