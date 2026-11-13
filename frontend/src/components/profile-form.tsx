"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, ApiError, readable } from "@/lib/api";
import type { Experience, FieldRegistry, FieldSpec, Institution, InstitutionSelection, Profile, ProfileValue } from "@/types/api";

type DraftValue = ProfileValue | "" | undefined;

const emptyExperience = (): Experience => ({
  kind: "activity",
  organization: "",
  title: "",
  description: "",
  start_date: null,
  end_date: null,
  current: false,
  hours: null,
  leadership: false,
  tags: [],
});

// These values come from one official institution record and must be updated together.
const institutionFieldNames = new Set(["school", "school_id", "school_city", "school_state"]);

function isUnknown(value: DraftValue): value is { status: "unknown" } {
  return typeof value === "object" && value !== null && !Array.isArray(value) && value.status === "unknown";
}

function scalarValue(value: DraftValue): string {
  if (value === undefined || value === "" || isUnknown(value) || Array.isArray(value)) return "";
  return String(value);
}

function AnswerField({ name, spec, value, onChange }: {
  name: string;
  spec: FieldSpec;
  value: DraftValue;
  onChange: (value: DraftValue) => void;
}) {
  const unknown = isUnknown(value);
  const controlId = `field-${name}`;

  return <div className="field-row">
    <div className="field-label"><span>{spec.label}</span><small>{spec.sensitive ? "Sensitive · stored locally" : spec.optional ? "Optional" : "Core profile"}</small></div>
    {spec.type === "choice" && <select id={controlId} aria-label={spec.label} value={unknown ? "__unknown__" : scalarValue(value)} onChange={(event) => onChange(event.target.value === "__unknown__" ? { status: "unknown" } : event.target.value || undefined)}>
      <option value="">Select an answer</option>
      {spec.values?.map(option => <option key={option} value={option}>{readable(option)}</option>)}
      {spec.allow_unknown && <option value="__unknown__">I don&apos;t know</option>}
    </select>}
    {spec.type === "boolean" && <fieldset id={controlId} className="choice-grid"><legend className="sr-only">{spec.label}</legend>
      <label className="check-option"><input type="radio" name={name} checked={value === true} onChange={() => onChange(true)} />Yes</label>
      <label className="check-option"><input type="radio" name={name} checked={value === false} onChange={() => onChange(false)} />No</label>
      {spec.allow_unknown && <label className="check-option"><input type="radio" name={name} checked={unknown} onChange={() => onChange({ status: "unknown" })} />I don&apos;t know</label>}
      <label className="check-option"><input type="radio" name={name} checked={value === undefined || value === ""} onChange={() => onChange(undefined)} />Leave unanswered</label>
    </fieldset>}
    {spec.type === "multi_choice" && <fieldset id={controlId} className="choice-grid"><legend className="sr-only">{spec.label}</legend>
      {spec.values?.map(option => {
        const selected = Array.isArray(value) && value.includes(option);
        return <label className="check-option" key={option}><input type="checkbox" checked={selected} onChange={(event) => {
          const current = Array.isArray(value) ? value : [];
          const next = event.target.checked ? [...current, option] : current.filter(item => item !== option);
          onChange(next.length > 0 ? next : undefined);
        }} />{readable(option)}</label>;
      })}
      {spec.allow_unknown && <label className="check-option"><input type="checkbox" checked={unknown} onChange={(event) => onChange(event.target.checked ? { status: "unknown" } : undefined)} />I don&apos;t know</label>}
    </fieldset>}
    {!["choice", "boolean", "multi_choice"].includes(spec.type) && <>
      <input
      id={controlId}
      aria-label={spec.label}
      type={spec.type === "email" ? "email" : spec.type === "date" ? "date" : spec.type === "month" ? "month" : ["integer", "number"].includes(spec.type) ? "number" : "text"}
      step={spec.type === "number" ? "any" : undefined}
      maxLength={spec.maximum}
      value={scalarValue(value)}
      onChange={(event) => onChange(["integer", "number"].includes(spec.type) && event.target.value !== "" ? Number(event.target.value) : event.target.value)}
      disabled={unknown}
      />
      {spec.allow_unknown && <label className="unknown-option"><input type="checkbox" checked={unknown} onChange={(event) => onChange(event.target.checked ? { status: "unknown" } : undefined)} />I don&apos;t know</label>}
    </>}
    {unknown && <p className="field-help">Saved as explicitly unknown. This can produce a Possible match rather than assuming an answer.</p>}
  </div>;
}

function ExperienceEditor({ item, index, update, remove }: { item: Experience; index: number; update: (item: Experience) => void; remove: () => void }) {
  return <article className="experience-card">
    <div className="experience-heading"><h3>Experience {index + 1}</h3><button type="button" className="button button-outline" onClick={remove}>Remove</button></div>
    <div className="experience-grid">
      <label>Type<select aria-label={`Experience ${index + 1} type`} value={item.kind} onChange={event => update({ ...item, kind: event.target.value as Experience["kind"] })}>
        {(["activity", "employment", "volunteering", "membership", "leadership", "honor"] as const).map(kind => <option value={kind} key={kind}>{readable(kind)}</option>)}
      </select></label>
      <label>Organization<input aria-label={`Experience ${index + 1} organization`} value={item.organization} required onChange={event => update({ ...item, organization: event.target.value })} /></label>
      <label>Role or title<input aria-label={`Experience ${index + 1} title`} value={item.title} required onChange={event => update({ ...item, title: event.target.value })} /></label>
      <label>Hours<input aria-label={`Experience ${index + 1} hours`} type="number" min="0" value={item.hours ?? ""} onChange={event => update({ ...item, hours: event.target.value ? Number(event.target.value) : null })} /></label>
      <label>Start date<input aria-label={`Experience ${index + 1} start date`} type="date" value={item.start_date ?? ""} onChange={event => update({ ...item, start_date: event.target.value || null })} /></label>
      <label>End date<input aria-label={`Experience ${index + 1} end date`} type="date" disabled={item.current} value={item.end_date ?? ""} onChange={event => update({ ...item, end_date: event.target.value || null })} /></label>
    </div>
    <label className="experience-description">Description<textarea aria-label={`Experience ${index + 1} description`} value={item.description ?? ""} onChange={event => update({ ...item, description: event.target.value })} /></label>
    <label className="check-option"><input type="checkbox" checked={item.current} onChange={event => update({ ...item, current: event.target.checked, end_date: event.target.checked ? null : item.end_date })} />I currently participate</label>
    <label className="check-option"><input type="checkbox" checked={item.leadership} onChange={event => update({ ...item, leadership: event.target.checked })} />This includes leadership</label>
    <label className="experience-description">Tags, separated by commas<input aria-label={`Experience ${index + 1} tags`} value={item.tags.join(", ")} onChange={event => update({ ...item, tags: event.target.value.split(",").map(tag => tag.trim().toLowerCase()).filter(Boolean) })} /></label>
  </article>;
}

export function ProfileForm() {
  const [registry, setRegistry] = useState<FieldRegistry | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [fields, setFields] = useState<Record<string, DraftValue>>({});
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [institutionQuery, setInstitutionQuery] = useState("");
  const [institutionResults, setInstitutionResults] = useState<Institution[]>([]);
  const [searchingInstitutions, setSearchingInstitutions] = useState(false);
  const [selectingInstitution, setSelectingInstitution] = useState("");

  useEffect(() => {
    Promise.all([api<FieldRegistry>("/api/profile-fields"), api<Profile>("/api/profile")])
      .then(([nextRegistry, nextProfile]) => { setRegistry(nextRegistry); setProfile(nextProfile); setFields(nextProfile.fields); setExperiences(nextProfile.experiences); })
      .catch(() => setError("Profile unavailable. Check that the local backend is running."));
  }, []);

  const sections = useMemo(() => registry?.sections.map(section => ({
    ...section,
    fields: Object.entries(registry.fields).filter(([name, spec]) => spec.section === section.id && !institutionFieldNames.has(name)),
  })) ?? [], [registry]);

  async function searchInstitutions() {
    const query = institutionQuery.trim();
    if (query.length < 2) {
      setError("Enter at least two characters of your college name.");
      return;
    }
    setSearchingInstitutions(true); setError(""); setMessage("");
    try {
      const results = await api<Institution[]>(`/api/institutions?q=${encodeURIComponent(query)}`);
      setInstitutionResults(results);
      if (results.length === 0) setError("No matching colleges were found in the local institution directory.");
    } catch {
      setError("The institution directory could not be searched.");
    } finally { setSearchingInstitutions(false); }
  }

  async function selectInstitution(item: Institution) {
    setSelectingInstitution(item.unit_id); setError(""); setMessage("");
    try {
      // The backend persists all four school fields atomically so matching never sees a partial school record.
      await api<InstitutionSelection>(`/api/institutions/${item.unit_id}/select`, { method: "POST" });
      const nextProfile = await api<Profile>("/api/profile");
      setProfile(nextProfile); setFields(nextProfile.fields); setInstitutionResults([]); setInstitutionQuery("");
      setMessage(`${item.name} selected. Its institution identifier was filled automatically.`);
    } catch {
      setError("The college could not be selected.");
    } finally { setSelectingInstitution(""); }
  }

  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setMessage(""); setError("");
    const patchFields = Object.fromEntries(Object.keys(registry?.fields ?? {}).map(name => [name, fields[name] === undefined || fields[name] === "" ? null : fields[name]]));
    try {
      const next = await api<Profile>("/api/profile", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: patchFields, experiences }) });
      setProfile(next); setFields(next.fields); setExperiences(next.experiences);
      setMessage(next.school_changed ? "Profile saved. Your school changed, so its scholarship sources will need confirmation." : "Profile saved locally.");
    } catch (caught) {
      setError(caught instanceof ApiError && caught.field ? `Check ${readable(caught.field)}.` : "The profile could not be saved.");
    } finally { setSaving(false); }
  }

  async function clearProfile() {
    if (!window.confirm("Clear every profile answer and experience from this Mac?")) return;
    try {
      await api<void>("/api/profile", { method: "DELETE" });
      setFields({}); setExperiences([]); setProfile(prev => prev ? { ...prev, fields: {}, experiences: [], completeness: { known: 0, unknown: 0, unanswered: registry ? Object.keys(registry.fields).length : 0, total: registry ? Object.keys(registry.fields).length : 0, percent_known: 0 } } : prev);
      setMessage("Profile cleared from local storage."); setError("");
    } catch { setError("The profile could not be cleared."); }
  }

  if (!registry && !error) return <section className="skeleton-panel" aria-label="Loading profile" />;
  if (!registry) return <section className="empty-panel"><h1>Profile unavailable</h1><p>{error}</p></section>;

  return <>
    <div className="page-heading"><div><p className="eyebrow">Private local matching data</p><h1>Your profile</h1><p>Complete what you know once. Unanswered and explicitly unknown have different matching meanings, and sensitive answers stay in your local PathAid database.</p></div></div>
    {profile && <section className="profile-summary" aria-label="Profile completeness"><strong>{profile.completeness.percent_known}% known</strong><span>{profile.completeness.known} answered · {profile.completeness.unknown} explicitly unknown · {profile.completeness.unanswered} unanswered</span></section>}
    <form className="profile-form" onSubmit={save}>
      {sections.map(section => <section className="form-card" key={section.id}><div className="form-card-heading"><p className="eyebrow">Profile</p><h2>{section.label}</h2></div>
        {section.id === "school" && <div className="institution-picker">
          <div className="selected-institution">
            <div><span>Selected college</span><strong>{scalarValue(fields.school) || "No official college selected"}</strong></div>
            {fields.school_id && !isUnknown(fields.school_id) && <dl>
              <div><dt>Institution identifier</dt><dd>{scalarValue(fields.school_id)}</dd></div>
              <div><dt>Location</dt><dd>{[scalarValue(fields.school_city), scalarValue(fields.school_state)].filter(Boolean).join(", ") || "Not listed"}</dd></div>
            </dl>}
            {!fields.school_id && fields.school && <p className="field-help">This school name is not linked to an official institution record yet. Search and select it below.</p>}
          </div>
          <label>Search for your college
            <div className="institution-search-row"><input aria-label="Search for your college" value={institutionQuery} onChange={event => setInstitutionQuery(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); void searchInstitutions(); } }} placeholder="Start typing a college name" /><button type="button" className="button button-outline" disabled={searchingInstitutions} onClick={searchInstitutions}>{searchingInstitutions ? "Searching…" : "Search"}</button></div>
          </label>
          {institutionResults.length > 0 && <div className="institution-results" aria-label="College search results">{institutionResults.map(item => <article key={item.unit_id}>
            <div><strong>{item.name}</strong><span>{item.city}, {item.state} · Institution ID {item.unit_id}</span></div>
            <button type="button" className="button button-outline" disabled={Boolean(selectingInstitution)} onClick={() => selectInstitution(item)}>{selectingInstitution === item.unit_id ? "Selecting…" : "Select"}</button>
          </article>)}</div>}
        </div>}
        {section.fields.map(([name, spec]) => <AnswerField key={name} name={name} spec={spec} value={fields[name]} onChange={value => setFields(current => ({ ...current, [name]: value }))} />)}
      </section>)}
      <section className="form-card"><div className="form-card-heading"><p className="eyebrow">Experiences</p><h2>Activities, work, service, memberships, and leadership</h2><p className="field-help">Structured experiences let deterministic rules find requirements without guessing from a biography.</p></div>
        <div className="experience-list">{experiences.map((item, index) => <ExperienceEditor key={item.id ?? index} item={item} index={index} update={next => setExperiences(current => current.map((value, position) => position === index ? next : value))} remove={() => setExperiences(current => current.filter((_, position) => position !== index))} />)}</div>
        <button type="button" className="button button-outline" onClick={() => setExperiences(current => [...current, emptyExperience()])}>Add experience</button>
      </section>
      {message && <p className="form-success" role="status">{message}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-actions"><button className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button></div>
    </form>
    <section className="danger-zone"><div><h2>Clear local profile</h2><p>Remove all profile answers and experiences without deleting the application.</p></div><button type="button" className="button button-danger" onClick={clearProfile}>Clear profile</button></section>
  </>;
}
