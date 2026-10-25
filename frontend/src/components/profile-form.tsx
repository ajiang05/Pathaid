"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, readable } from "@/lib/api";
import { useSession } from "@/components/session-provider";
import type { FieldRegistry, FieldSpec, Profile, ProfileFields } from "@/types/api";

const CORE=["school","state","study_level","enrollment","assistance_categories"];
const FEATURED_SCHOOLS=[
  "Amherst College",
  "Arizona State University",
  "Babson College",
  "Berklee College of Music",
  "Boston College",
  "Boston University",
  "Brandeis University",
  "Bridgewater State University",
  "Bunker Hill Community College",
  "California State University, Los Angeles",
  "City College of New York",
  "Emerson College",
  "Framingham State University",
  "Harvard University",
  "Howard University",
  "Holyoke Community College",
  "Massachusetts Bay Community College",
  "Massachusetts College of Art and Design",
  "Massachusetts Institute of Technology",
  "Miami Dade College",
  "Mount Holyoke College",
  "New York University",
  "Northeastern University",
  "Ohio State University",
  "Pennsylvania State University",
  "Salem State University",
  "Smith College",
  "Spelman College",
  "Springfield Technical Community College",
  "Suffolk University",
  "Tufts University",
  "University of California, Berkeley",
  "University of California, Los Angeles",
  "University of Chicago",
  "University of Florida",
  "University of Massachusetts Amherst",
  "University of Massachusetts Boston",
  "University of Massachusetts Dartmouth",
  "University of Massachusetts Lowell",
  "University of Michigan",
  "University of Texas at Austin",
  "University of Washington",
  "Wellesley College",
  "Williams College",
  "Worcester Polytechnic Institute",
  "Worcester State University",
  "Yale University",
];
const OTHER_SCHOOL="__other__";

function SchoolField({value,onChange}:{value:ProfileFields[string];onChange:(value:ProfileFields[string])=>void}) {
  const school=typeof value==="string"?value:"";
  const [otherSelected,setOtherSelected]=useState(Boolean(school&&!FEATURED_SCHOOLS.includes(school)));
  const selection=otherSelected?OTHER_SCHOOL:FEATURED_SCHOOLS.includes(school)?school:"";

  function selectSchool(next:string) {
    if(next===OTHER_SCHOOL){setOtherSelected(true);onChange("");return;}
    setOtherSelected(false);onChange(next||null);
  }

  return <>
    <select id="school" value={selection} onChange={event=>selectSchool(event.target.value)}>
      <option value="">Select your college</option>
      {FEATURED_SCHOOLS.map(name=><option value={name} key={name}>{name}</option>)}
      <option value={OTHER_SCHOOL}>Other</option>
    </select>
    {otherSelected&&<div className="school-other-field">
      <label htmlFor="school-other">Enter your college name</label>
      <input id="school-other" type="text" value={school} onChange={event=>onChange(event.target.value)} required maxLength={120} autoComplete="organization" />
    </div>}
  </>;
}

function Field({name,spec,value,onChange}:{name:string;spec:FieldSpec;value:ProfileFields[string];onChange:(value:ProfileFields[string])=>void}) {
  const described=spec.sensitive?`${name}-help`:undefined;
  if(name==="school") return <SchoolField value={value} onChange={onChange}/>;
  if(spec.type==="choice") return <select id={name} value={typeof value==="string"?value:""} onChange={e=>onChange(e.target.value||null)} aria-describedby={described}><option value="">I don&apos;t know / prefer not to answer</option>{spec.values?.map(v=><option value={v} key={v}>{readable(v)}</option>)}</select>;
  if(spec.type==="multi_choice") { const selected=Array.isArray(value)?value:[]; return <fieldset className="choice-grid"><legend className="sr-only">{spec.question}</legend>{spec.values?.map(v=><label className="check-option" key={v}><input type="checkbox" checked={selected.includes(v)} onChange={e=>onChange(e.target.checked?[...selected,v]:selected.filter(item=>item!==v))}/><span>{readable(v)}</span></label>)}</fieldset>; }
  if(spec.type==="boolean") return <select id={name} value={typeof value==="boolean"?String(value):""} onChange={e=>onChange(e.target.value===""?null:e.target.value==="true")} aria-describedby={described}><option value="">I don&apos;t know / prefer not to answer</option><option value="true">Yes</option><option value="false">No</option></select>;
  return <input id={name} type={spec.type==="integer"||spec.type==="number"?"number":"text"} step={spec.type==="number"?"0.01":undefined} value={typeof value==="string"||typeof value==="number"?value:""} onChange={e=>onChange(e.target.value===""?null:spec.type==="number"?Number(e.target.value):spec.type==="integer"?Number.parseInt(e.target.value,10):e.target.value)} aria-describedby={described}/>;
}

export function ProfileForm({mode}:{mode:"onboarding"|"profile"}) {
  const router=useRouter(); const session=useSession();
  const [registry,setRegistry]=useState<FieldRegistry|null>(null); const [values,setValues]=useState<ProfileFields>({});
  const [optIn,setOptIn]=useState(false); const [status,setStatus]=useState<"loading"|"idle"|"saving"|"saved"|"error">("loading"); const [message,setMessage]=useState(""); const [confirmDelete,setConfirmDelete]=useState(false);
  useEffect(()=>{ if(session.status!=="authenticated")return; Promise.all([api<FieldRegistry>("/api/profile-fields"),api<Profile>("/api/profile")]).then(([r,p])=>{setRegistry(r);setValues(p.fields);setOptIn(p.ai_opt_in);setStatus("idle")}).catch(()=>{setStatus("error");setMessage("We could not load your profile. Try again shortly.")}); },[session.status]);
  const names=useMemo(()=>mode==="onboarding"?CORE:registry?Object.keys(registry.fields):[],[mode,registry]);
  function update(name:string,value:ProfileFields[string]){setValues(current=>({...current,[name]:value}));setStatus("idle");}
  async function save(event:React.FormEvent){event.preventDefault();if(!registry||!session.csrf)return;setStatus("saving");setMessage("");const fields:ProfileFields={};for(const name of names){const value=values[name];fields[name]=Array.isArray(value)&&value.length===0?null:value??null;}try{await api<Profile>("/api/profile",{method:"PATCH",headers:{"Content-Type":"application/json","X-CSRF-Token":session.csrf},body:JSON.stringify({fields,ai_opt_in:mode==="profile"?optIn:undefined})});setStatus("saved");if(mode==="onboarding")router.push("/discover");}catch(error){setStatus("error");setMessage(error instanceof ApiError&&error.field?`Check ${readable(error.field)} and try again.`:"Your changes could not be saved. Review the form and try again.");}}
  async function deleteAccount(){if(!session.csrf)return;setStatus("saving");try{await api<void>("/api/profile",{method:"DELETE",headers:{"X-CSRF-Token":session.csrf}});router.push("/");router.refresh();}catch{setStatus("error");setMessage("Your account could not be deleted. Try again.");setConfirmDelete(false);}}
  if(status==="loading")return <section className="skeleton-panel" aria-label="Loading profile"/>;
  if(!registry)return <section className="empty-panel"><h1>Profile unavailable</h1><p>{message}</p></section>;
  const academicNames=names.filter(name=>CORE.includes(name));
  const optionalNames=names.filter(name=>!CORE.includes(name));
  const renderField=(name:string)=>{const spec=registry.fields[name];return <div className="field-row" key={name}><label htmlFor={spec.type==="multi_choice"?undefined:name}>{spec.question}<span>{spec.progressive?"Optional":""}</span></label><Field name={name} spec={spec} value={values[name]} onChange={value=>update(name,value)}/>{spec.sensitive&&<p className="field-help" id={`${name}-help`}>Optional sensitive information. Skip or remove it at any time.</p>}</div>};
  return <>
    <div className="page-heading"><div><p className="eyebrow">{mode==="onboarding"?"Step 1 of 1":"Student profile"}</p><h1>{mode==="onboarding"?"Tell us what support fits your situation":"Profile and privacy"}</h1><p>{mode==="onboarding"?"These basics help PathAid select relevant reviewed programs. You can change them later.":"Update saved answers and control optional AI explanations."}</p></div></div>
    <form className="profile-form" onSubmit={save}>
      <section className="form-card"><div className="form-card-heading"><span className="step-badge">{mode==="onboarding"?"Core profile":"Saved answers"}</span><h2>Academic background and support</h2></div>
        {academicNames.map(renderField)}
      </section>
      {mode==="profile"&&<section className="form-card"><div className="form-card-heading"><span className="step-badge">Optional</span><h2>Additional eligibility details</h2><p>These answers can make scholarship results more precise. You can skip or remove any answer.</p></div>{optionalNames.map(renderField)}</section>}
      {mode==="profile"&&<section className="form-card"><div className="form-card-heading"><span className="step-badge">Privacy</span><h2>Optional recommendation assistance</h2></div><label className="consent-option"><input type="checkbox" checked={optIn} onChange={e=>setOptIn(e.target.checked)}/><span><strong>Allow AI-assisted scholarship explanations</strong><small>PathAid sends only relevant profile fields and reviewed program facts. Eligibility and ranking remain deterministic.</small></span></label></section>}
      {message&&<div className="form-error" role="alert">{message}</div>}{status==="saved"&&<div className="form-success" role="status">Your profile changes were saved.</div>}
      <div className="form-actions"><button className="button button-primary" disabled={status==="saving"}>{status==="saving"?"Saving…":mode==="onboarding"?"Save and find support":"Save changes"}</button></div>
    </form>
    {mode==="profile"&&<section className="danger-zone"><div><h2>Delete account</h2><p>Permanently removes your profile, sessions, and recommendation usage records.</p></div>{confirmDelete?<div className="delete-actions"><button className="button button-danger" onClick={()=>void deleteAccount()}>Permanently delete</button><button className="button button-quiet" onClick={()=>setConfirmDelete(false)}>Cancel</button></div>:<button className="button button-outline" onClick={()=>setConfirmDelete(true)}>Delete my account</button>}</section>}
  </>;
}
